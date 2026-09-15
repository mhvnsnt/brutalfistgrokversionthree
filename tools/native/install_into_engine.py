#!/usr/bin/env python3
"""Install chara_bannon into the Schwarzerblitz engine media tree.

This is the folder the native executable loads:
  schwarzerblitz_engine/bin/media/characters/<id>/
  Mesh1/<file.x> via smgr->getMesh()
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "native" / "media" / "characters" / "chara_bannon"
TARGETS = [
    ROOT / "native" / "schwarzerblitz_engine" / "bin" / "media" / "characters",
    ROOT / "vendor" / "SchwarzerblitzEngine" / "schwarzerblitz_engine" / "bin" / "media" / "characters",
]


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    mesh = dst / "Mesh1"
    # Engine sample uses FightPreview.png (Windows-insensitive); keep both.
    fp = mesh / "FightPreview.png"
    src_fp = dst / "fightPreview.png"
    if src_fp.exists() and not fp.exists():
        shutil.copy2(src_fp, fp)


def upsert_roster(roster: Path) -> None:
    lines = []
    if roster.exists():
        lines = [ln.rstrip("\n") for ln in roster.read_text().splitlines() if ln.strip()]
    kept = [ln for ln in lines if not ln.lower().startswith("chara_bannon")]
    kept.insert(0, "chara_bannon    0")
    roster.write_text("\n".join(kept) + "\n", encoding="ascii")


def main() -> None:
    if not (SRC / "Mesh1" / "BF_bannon.x").exists():
        raise SystemExit("Run build-bannon-character first")
    for target in TARGETS:
        if not target.parent.exists() and "vendor" in str(target):
            continue
        target.mkdir(parents=True, exist_ok=True)
        copy_tree(SRC, target / "chara_bannon")
        upsert_roster(target / "roster.ini")
        print(f"installed {target / 'chara_bannon'}")


if __name__ == "__main__":
    main()
