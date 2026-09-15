#!/usr/bin/env python3
"""Bind exported real mocap .x clips into the Schwarzerblitz character files.

Never invents motion. If a desired clip did not export, the field is left on
the already-converted Bannon GLB locomotion (idle/walkFast/running) or reported
missing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAR = ROOT / "native" / "media" / "characters" / "chara_bannon"
ANIM = CHAR / "animations"
REPORT = ROOT / "native" / "qa" / "mocap-export-report.json"

# Engine animation name -> preferred mocap clip titles (first exported wins).
ALIASES = {
    "jab": ["Combo Punch", "Illegal Elbow Punch", "Illegal Elbow Punch (1)"],
    "heavy": ["Drop Kick", "Hurricane Kick", "Illegal Knee"],
    "hitReaction": ["Hit Reaction", "Hit To Body", "Hit To Head"],
    "knockdown": ["Falling Flat Impact", "Falling Forward Death", "Defeat"],
    "block": ["Center Block"],
    "evade": ["Corkscrew Evade", "Esquiva 4"],
    "taunt": ["Capoeira", "Ginga Backward", "Ginga Sideways 2"],
}


def main() -> None:
    if not REPORT.exists():
        raise SystemExit("Run batch_export_mocap.py first")
    data = json.loads(REPORT.read_text())
    by_name = {
        row["clip"]: row
        for row in data.get("clips") or []
        if row.get("status") == "exported"
    }
    bound = []
    missing = []
    for engine_name, candidates in ALIASES.items():
        src = None
        picked = None
        for title in candidates:
            row = by_name.get(title)
            if not row:
                continue
            path = ROOT / row["x"]
            if path.exists():
                src = path
                picked = row
                break
        if src is None:
            missing.append({"engine": engine_name, "tried": candidates})
            continue
        dest = ANIM / f"{engine_name}.x"
        shutil.copy2(src, dest)
        bound.append(
            {
                "engine": engine_name,
                "clip": picked["clip"],
                "frames": picked.get("frames"),
                "x": str(dest.relative_to(ROOT)),
            }
        )

    jab = next((b for b in bound if b["engine"] == "jab"), None)
    heavy = next((b for b in bound if b["engine"] == "heavy"), None)
    hit = next((b for b in bound if b["engine"] == "hitReaction"), None)
    down = next((b for b in bound if b["engine"] == "knockdown"), None)

    moves = []
    if jab:
        end = max(8, int(jab["frames"] or 12) // 8)
        moves.append(
            "\n".join(
                [
                    "#MOVE Jab",
                    "#DISPLAY_NAME Jab",
                    "#RANGE 0.0 90.0",
                    "#ANIMATION jab",
                    f"#FRAMES 0 {end}",
                    "#STANCE Ground",
                    "#DELAY_AFTER_MOVE_MS 120",
                    "#INPUT",
                    "A",
                    "#INPUT_END",
                    "",
                ]
            )
        )
    if heavy:
        end = max(12, int(heavy["frames"] or 18) // 6)
        moves.append(
            "\n".join(
                [
                    "#MOVE Heavy",
                    "#DISPLAY_NAME Heavy",
                    "#RANGE 0.0 110.0",
                    "#ANIMATION heavy",
                    f"#FRAMES 0 {end}",
                    "#STANCE Ground",
                    "#DELAY_AFTER_MOVE_MS 200",
                    "#INPUT",
                    "B",
                    "#INPUT_END",
                    "",
                ]
            )
        )
    if moves:
        (CHAR / "moves.txt").write_text("\n".join(moves), encoding="ascii")

    # Keep GLB locomotion; overlay hit/knockdown when real mocap exists.
    char_path = CHAR / "character.txt"
    text = char_path.read_text()
    if hit:
        n = max(4, min(20, int(hit["frames"] or 8) // 10))
        for key in (
            "HITHIGHWEAKFRONT",
            "HITMEDWEAKFRONT",
            "HITLOWWEAKFRONT",
            "HITHIGHWEAKBACK",
            "HITMEDWEAKBACK",
            "HITLOWWEAKBACK",
            "HITMEDSTRONG",
            "HITMEDSTRONGBACK",
            "HITLOWSTRONG",
            "HITLOWSTRONGBACK",
            "HITHIGHSTRONG",
            "HITHIGHSTRONGBACK",
            "HITFLIGHTSTRONG",
            "HITFLIGHTSTRONGBACK",
        ):
            text = replace_line(text, key, f"hitReaction 0 {n}")
    if down:
        n = max(6, min(40, int(down["frames"] or 8) // 6))
        for key in (
            "GROUNDEDSUPINE",
            "GROUNDEDPRONE",
            "GROUNDEDSUPINEROTATION",
            "GROUNDEDPRONEROTATION",
            "SUPINELANDING",
        ):
            text = replace_line(text, key, f"knockdown 0 {n}")
    char_path.write_text(text, encoding="ascii")

    out = {
        "policy": "REAL_FBX_ONLY aliases into engine animation names",
        "bound": bound,
        "missing": missing,
    }
    (ROOT / "native" / "qa" / "engine-anim-bind.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(json.dumps({"bound": len(bound), "missing": len(missing)}, indent=2))


def replace_line(text: str, key: str, value: str) -> str:
    token = f"#{key} "
    lines = []
    for line in text.splitlines():
        if line.startswith(token):
            lines.append(f"#{key} {value}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
