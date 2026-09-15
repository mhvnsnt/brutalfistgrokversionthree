#!/usr/bin/env bash
# Linux counterpart of tools/native/build-bannon-character.ps1
# Canonical Bannon GLB → DirectX .x skeletal resource the Schwarzerblitz
# executable loads via Irrlicht ISkinnedMesh (smgr->getMesh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
CHAR_ID="${1:-bannon}"
if [[ "$CHAR_ID" != "bannon" ]]; then
  echo "This sandbox currently converts the proven BANNON_rigged.glb master."
  echo "Other real-GLB fighters follow the same .ps1/.sh once QA-gated."
fi
python3 tools/native/glb_to_directx_x.py \
  --glb native/source/BANNON_rigged.uncompressed.glb \
  --out native/media/characters \
  --public public/native
python3 tools/native/install_into_engine.py
python3 tools/native/software_render_x.py
python3 - <<'PY'
from pathlib import Path
cfg = Path("native/media/characters/chara_bannon/Mesh1/config.txt")
x = Path("native/media/characters/chara_bannon/Mesh1/BF_bannon.x")
text = cfg.read_text()
for key in ("#MESH_FILENAME", "#OUTFIT_NAME", "#CHARACTER_NAME"):
    if key not in text:
        raise SystemExit(f"Missing {key}")
if x.stat().st_size < 1024:
    raise SystemExit("Suspiciously small .x mesh")
print(f"PASS native resource: {x.parent.parent}")
PY
