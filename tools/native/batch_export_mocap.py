#!/usr/bin/env python3
"""Batch-export Bannon mocap FBX through the animation bridge into DirectX .x.

Does not invent clips. Character-rig FBX, Git-LFS pointer stubs, and UTF-8
corrupted binaries are reported rather than replaced with procedural motion.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNON = ROOT / "BannonSource"
if not BANNON.exists():
    BANNON = Path("/workspace/vendor/Bannon")
FBX_ROOT = BANNON / "assets" / "mocap"
MAP_PATH = BANNON / "assets" / "moves" / "fbx_move_map.json"
DUMP = ROOT / "tools" / "native" / "fbx_dump_anim"
OUT_ANIM = ROOT / "native" / "media" / "characters" / "chara_bannon" / "animations"
OUT_JSON = ROOT / "public" / "native" / "chara_bannon" / "clips"
ENGINE_ANIM = (
    ROOT
    / "native"
    / "schwarzerblitz_engine"
    / "bin"
    / "media"
    / "characters"
    / "chara_bannon"
    / "animations"
)
QA = ROOT / "native" / "qa"

SKIP_CATS = {"character_rig"}
MAX_FBX_BYTES = 28 * 1024 * 1024
VIEWER_BUDGET = 36
VIEWER_CAT_PRIORITY = (
    "strike",
    "locomotion",
    "reaction",
    "knockdown",
    "defense",
    "getup",
    "grapple",
    "taunt",
    "aerial_transition",
    "style_stance",
    "submission",
    "dive",
    "weapon",
    "rope_transition",
    "irish_whip",
    "misc",
)


def slug(name: str) -> str:
    s = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_") or "clip"


def is_lfs_pointer(path: Path) -> bool:
    try:
        head = path.read_bytes()[:40]
    except OSError:
        return True
    return head.startswith(b"version https://git-lfs")


def is_utf8_corrupt(path: Path) -> bool:
    """Git/text conversion replaced binary bytes with U+FFFD (ef bf bd)."""
    try:
        head = path.read_bytes()[:8192]
    except OSError:
        return True
    return b"\xef\xbf\xbd" in head


def index_fbx() -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not FBX_ROOT.exists():
        return found
    for p in FBX_ROOT.rglob("*.fbx"):
        key = p.stem.lower()
        if key in found:
            if "drive" in str(p) and "drive" not in str(found[key]):
                found[key] = p
            continue
        found[key] = p
    return found


def load_mesh_skeleton():
    sys.path.insert(0, str(ROOT / "tools" / "native"))
    from glb_to_directx_x import (  # type: ignore
        load_glb,
        sanitize,
        write_frame,
    )

    glb = ROOT / "native" / "source" / "BANNON_rigged.uncompressed.glb"
    if not glb.exists():
        glb = ROOT / "native" / "source" / "BANNON_rigged.glb"
    g, blob = load_glb(glb)
    nodes = g.get("nodes") or []
    children_of: dict[int, list[int]] = defaultdict(list)
    parents: dict[int, int] = {}
    for i, node in enumerate(nodes):
        for c in node.get("children") or []:
            children_of[i].append(c)
            parents[c] = i
    hips = g["skins"][0]["joints"][0]
    armature_idx = parents.get(hips, hips)
    return {
        "g": g,
        "blob": blob,
        "nodes": nodes,
        "children_of": children_of,
        "armature_idx": armature_idx,
        "write_frame": write_frame,
        "sanitize": sanitize,
        "names": {sanitize(n.get("name")) for n in nodes},
    }


def tracks_to_x(skel: dict, tracks: dict, fps: int, frame_count: int) -> tuple[str, int]:
    write_frame = skel["write_frame"]
    fmt = "{: .6f}".format
    lines = [
        "xof 0303txt 0032",
        "",
        "Frame Root {",
        "  FrameTransformMatrix {",
        "     1.000000, 0.000000, 0.000000, 0.000000,",
        "     0.000000, 1.000000, 0.000000, 0.000000,",
        "     0.000000, 0.000000, 1.000000, 0.000000,",
        "     0.000000, 0.000000, 0.000000, 1.000000;;",
        "  }",
        write_frame(skel["armature_idx"], skel["nodes"], skel["children_of"], "  "),
        "}",
        "",
        "AnimationSet Global {",
    ]
    mesh_names = skel["names"]
    used = 0
    for bone, data in tracks.items():
        if bone not in mesh_names:
            continue
        rots = data.get("r") or []
        pos = data.get("t") or []
        if not rots:
            continue
        used += 1
        lines.append("  Animation {")
        lines.append(f"    {{{bone}}}")
        lines.append("    AnimationKey { // Rotation")
        lines.append("      0;")
        lines.append(f"      {len(rots)};")
        for i, val in enumerate(rots):
            end = ";;," if i < len(rots) - 1 else ";;;"
            if len(val) == 4:
                x, y, z, w = val
                fr = i
            else:
                fr, x, y, z, w = val[0], val[1], val[2], val[3], val[4]
            lines.append(
                f"      {int(fr)};4; {fmt(x)},{fmt(y)},{fmt(z)},{fmt(w)}{end}"
            )
        lines.append("    }")
        if pos:
            lines.append("    AnimationKey { // Position")
            lines.append("      2;")
            lines.append(f"      {len(pos)};")
            for i, val in enumerate(pos):
                end = ";;," if i < len(pos) - 1 else ";;;"
                if len(val) == 3:
                    x, y, z = val
                    fr = i
                else:
                    fr, x, y, z = val[0], val[1], val[2], val[3]
                lines.append(f"      {int(fr)};3; {fmt(x)},{fmt(y)},{fmt(z)}{end}")
            lines.append("    }")
        lines.append("  }")
    lines.append("} // End of AnimationSet Global")
    lines.append("")
    if used < 8:
        raise ValueError(f"only {used} bones matched the Bannon Mixamo skeleton")
    return "\n".join(lines), used


def dump_fbx(path: Path) -> dict:
    proc = subprocess.run(
        [str(DUMP), str(path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"fbx_dump_anim failed ({proc.returncode})")
    return json.loads(proc.stdout)


def compact_viewer(tracks: dict, fps: int, frames: int, duration: float) -> dict:
    out_tracks = {}
    step = 1 if frames <= 180 else 2
    for bone, data in tracks.items():
        rots = data.get("r") or []
        pos = data.get("t") or []
        r = [rots[i] for i in range(0, len(rots), step)]
        entry = {"r": [[round(x, 5) for x in q] for q in r]}
        if "hips" in bone.lower():
            t = [pos[i] for i in range(0, len(pos), step)] if pos else []
            entry["t"] = [[round(x, 5) for x in p] for p in t]
        out_tracks[bone] = entry
    return {
        "fps": fps / step,
        "frames": len(next(iter(out_tracks.values()))["r"]) if out_tracks else 0,
        "duration": duration,
        "tracks": out_tracks,
    }


def find_fbx(name: str, fbx_index: dict[str, Path]) -> Path | None:
    fbx = fbx_index.get(name.lower())
    if fbx is not None:
        return fbx
    key = "".join(ch for ch in name.lower() if ch.isalnum())
    for k, p in fbx_index.items():
        if "".join(ch for ch in k if ch.isalnum()) == key:
            return p
    return None


def main() -> None:
    if not DUMP.exists():
        raise SystemExit(f"missing {DUMP} — compile fbx_dump_anim first")
    mapping = json.loads(MAP_PATH.read_text())
    clips = mapping.get("clips") or []
    fbx_index = index_fbx()
    skel = load_mesh_skeleton()
    OUT_ANIM.mkdir(parents=True, exist_ok=True)
    OUT_JSON.mkdir(parents=True, exist_ok=True)
    ENGINE_ANIM.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    rows = []
    for clip in clips:
        name = clip.get("clip") or ""
        cat = clip.get("cat") or "misc"
        engine = clip.get("engine") or ""
        pos = clip.get("pos") or ""
        rec = {
            "clip": name,
            "slug": slug(name),
            "cat": cat,
            "engine": engine,
            "pos": pos,
            "status": "pending",
        }
        if cat in SKIP_CATS:
            rec["status"] = "skipped_character_rig"
            rec["reason"] = "character_rig FBX is not motion data"
            rows.append(rec)
            continue
        fbx = find_fbx(name, fbx_index)
        if fbx is None:
            rec["status"] = "missing_fbx"
            rec["reason"] = "no matching FBX on disk"
            rows.append(rec)
            continue
        rec["fbx"] = str(fbx.relative_to(BANNON)) if fbx.is_relative_to(BANNON) else str(fbx)
        if is_lfs_pointer(fbx):
            rec["status"] = "missing_lfs"
            rec["reason"] = "Git LFS pointer, real FBX not fetched"
            rows.append(rec)
            continue
        if is_utf8_corrupt(fbx):
            rec["status"] = "corrupt_fbx"
            rec["reason"] = "binary FBX was UTF-8 corrupted (U+FFFD in header)"
            rows.append(rec)
            continue
        size = fbx.stat().st_size
        rec["bytes"] = size
        if size > MAX_FBX_BYTES:
            rec["status"] = "skipped_too_large"
            rec["reason"] = f"{size} bytes exceeds motion-clip budget"
            rows.append(rec)
            continue
        try:
            dumped = dump_fbx(fbx)
            x_text, used = tracks_to_x(
                skel, dumped["bones"], int(dumped["fps"]), int(dumped["frames"])
            )
            x_name = rec["slug"] + ".x"
            x_path = OUT_ANIM / x_name
            x_path.write_text(x_text, encoding="ascii")
            rec["status"] = "exported"
            rec["x"] = str(x_path.relative_to(ROOT))
            rec["bonesMatched"] = used
            rec["frames"] = dumped["frames"]
            rec["duration"] = dumped["duration"]
            rec["_tracks"] = dumped["bones"]
            rec["_fps"] = dumped["fps"]
        except Exception as exc:  # noqa: BLE001 — batch must continue
            rec["status"] = "failed"
            rec["reason"] = str(exc)[:400]
        rows.append(rec)
        print(f"{rec['status']:22} {name}", flush=True)

    # Viewer JSON: combat-first, still real clips only.
    exported = [r for r in rows if r["status"] == "exported"]
    exported.sort(
        key=lambda r: (
            VIEWER_CAT_PRIORITY.index(r["cat"])
            if r["cat"] in VIEWER_CAT_PRIORITY
            else 99,
            r["clip"],
        )
    )
    viewer_written = 0
    for rec in exported:
        if viewer_written >= VIEWER_BUDGET:
            rec.pop("_tracks", None)
            rec.pop("_fps", None)
            continue
        compact = compact_viewer(
            rec.pop("_tracks"), rec.pop("_fps"), rec["frames"], rec["duration"]
        )
        compact["clip"] = rec["clip"]
        compact["cat"] = rec["cat"]
        compact["x"] = rec["slug"] + ".x"
        compact["source"] = "real FBX mocap"
        (OUT_JSON / (rec["slug"] + ".json")).write_text(
            json.dumps(compact, separators=(",", ":"))
        )
        rec["viewer"] = f"clips/{rec['slug']}.json"
        viewer_written += 1

    summary = {
        "schema": 1,
        "source": "BannonSource/assets/moves/fbx_move_map.json",
        "policy": "REAL_FBX_ONLY — no procedural substitution",
        "counts": {
            "listed": len(rows),
            "exported": sum(1 for r in rows if r["status"] == "exported"),
            "missing_lfs": sum(1 for r in rows if r["status"] == "missing_lfs"),
            "missing_fbx": sum(1 for r in rows if r["status"] == "missing_fbx"),
            "corrupt_fbx": sum(1 for r in rows if r["status"] == "corrupt_fbx"),
            "skipped_character_rig": sum(
                1 for r in rows if r["status"] == "skipped_character_rig"
            ),
            "skipped_too_large": sum(1 for r in rows if r["status"] == "skipped_too_large"),
            "failed": sum(1 for r in rows if r["status"] == "failed"),
        },
        "clips": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
    }
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "mocap-export-report.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT_JSON / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["counts"], indent=2))


if __name__ == "__main__":
    main()
