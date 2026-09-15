param(
  [Parameter(Mandatory=$true)][string]$CharacterId,
  [string]$SourceGlb = "",
  [string]$OutRoot = "native/media/characters"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "."
$bannon = Join-Path $root "BannonSource"
$manifest = Join-Path $root "src/data/bannonCharacterManifest.json"
if (!(Test-Path $manifest)) { throw "Run npm run bannon:manifest first." }

$data = Get-Content $manifest -Raw | ConvertFrom-Json
$row = $data.eligible | Where-Object { $_.id -eq $CharacterId } | Select-Object -First 1
if (!$row) { throw "Character '$CharacterId' is not an eligible real-GLB Bannon fighter." }

if ([string]::IsNullOrWhiteSpace($SourceGlb)) {
  $SourceGlb = Join-Path $root ($row.model -replace '^BannonSource[/\\]', '')
  $SourceGlb = Join-Path $bannon ($row.model -replace '^BannonSource[/\\]', '')
}
if (!(Test-Path $SourceGlb)) { throw "GLB not found: $SourceGlb" }

$outDir = Join-Path $root (Join-Path $OutRoot ("chara_" + $CharacterId))
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outDir "Mesh1") | Out-Null

# Schwarzerblitz/Irrlicht expects DirectX skeletal .x character meshes.
# Assimp is used as the conversion boundary; the canonical GLB remains untouched.
$mesh = Join-Path $outDir ("BF_" + $CharacterId + ".x")
& assimp export $SourceGlb $mesh -f x
if ($LASTEXITCODE -ne 0) { throw "Assimp .x export failed for $CharacterId" }

@"
#MESH_FILENAME BF_$CharacterId.x
#OUTFIT_NAME $($row.name -replace ' ','_')
#AVAILABLE_FROM_START 1
#CHARACTER_NAME $($row.name -replace ' ','_')
#CHARACTER_SHORTNAME $($row.name -replace ' ','_')
#OUTFIT_MESH_SCALE 1.0
"@ | Set-Content -Encoding ASCII (Join-Path $outDir "Mesh1/config.txt")

@"
BannonId=$($row.id)
DisplayName=$($row.name)
Bio=$($row.bio)
SourceGLB=$($row.model)
Policy=REAL_GLB_ONLY
"@ | Set-Content -Encoding UTF8 (Join-Path $outDir "bannon.identity.txt")

Write-Host "Built native starter resource for $($row.name): $mesh"
