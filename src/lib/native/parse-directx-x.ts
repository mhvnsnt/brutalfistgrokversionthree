/** Minimal DirectX .x text parser for Schwarzerblitz/Irrlicht skeletal meshes. */

export type XBone = {
  name: string;
  parent: number;
  matrix: number[]; // 16 floats, DirectX row-major (translation in last row)
};

export type XMesh = {
  positions: Float32Array;
  normals: Float32Array;
  uvs: Float32Array;
  indices: Uint32Array;
  skinIndex: Uint16Array;
  skinWeight: Float32Array;
  bones: XBone[];
  textureName: string;
  vertexCount: number;
  triangleCount: number;
};

function stripComments(src: string): string {
  return src.replace(/\/\/[^\n]*/g, "");
}

function readMatrix(block: string): number[] {
  const nums = block.match(/-?\d+\.\d+|-?\d+/g);
  if (!nums || nums.length < 16) return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  return nums.slice(0, 16).map(Number);
}

function extractBalanced(src: string, openIdx: number): { inner: string; end: number } {
  let depth = 0;
  for (let i = openIdx; i < src.length; i++) {
    const ch = src[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return { inner: src.slice(openIdx + 1, i), end: i + 1 };
    }
  }
  throw new Error("Unbalanced brace in .x file");
}

function parseFrames(src: string): XBone[] {
  const bones: XBone[] = [];
  const stack: number[] = [];
  const re = /Frame\s+([A-Za-z0-9_]+)\s*\{/g;
  let match: RegExpExecArray | null;
  const consumed = new Set<number>();
  while ((match = re.exec(src))) {
    if (consumed.has(match.index)) continue;
    const name = match[1];
    if (name === "Root") continue;
    const brace = src.indexOf("{", match.index);
    const { inner, end } = extractBalanced(src, brace);
    consumed.add(match.index);
    const parent = stack.length ? stack[stack.length - 1] : -1;
    const mtxMatch = inner.match(/FrameTransformMatrix\s*\{([^}]*)\}/);
    const matrix = mtxMatch ? readMatrix(mtxMatch[1]) : [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    const idx = bones.length;
    bones.push({ name, parent, matrix });
    const childFrames = inner.match(/Frame\s+[A-Za-z0-9_]+\s*\{/g);
    if (childFrames && childFrames.length) {
      stack.push(idx);
      const nested = parseFrames(" " + inner);
      for (const child of nested) {
        if (child.parent === -1) child.parent = idx;
        bones.push(child);
      }
      stack.pop();
    }
    re.lastIndex = end;
  }
  return bones;
}

function parseMeshBlock(meshInner: string): Omit<XMesh, "bones"> {
  const tex = meshInner.match(/TextureFilename\s*\{\s*"([^"]+)"/);
  const textureName = tex?.[1] ?? "bannon.png";

  const body = meshInner.replace(/MeshNormals\s*\{[\s\S]*?\n\s*\}/, "")
    .replace(/MeshTextureCoords\s*\{[\s\S]*?\n\s*\}/, "")
    .replace(/MeshMaterialList\s*\{[\s\S]*$/, "");

  const nums = [...meshInner.matchAll(/-?\d+\.\d+|-?\d+/g)].map((m) => m[0]);
  // Safer: parse sections with dedicated regexes.
  const header = meshInner.match(/^\s*(\d+);/);
  if (!header) throw new Error("Mesh missing vertex count");
  const vertexCount = Number(header[1]);

  const vertSection = meshInner.slice(header.index! + header[0].length);
  const faceCountMatch = vertSection.match(/(\d+);(?=\s*3;)/);
  if (!faceCountMatch) throw new Error("Mesh missing face count");
  const triangleCount = Number(faceCountMatch[1]);

  const vertText = vertSection.slice(0, faceCountMatch.index);
  const vertNums = vertText.match(/-?\d+\.\d+|-?\d+/g);
  if (!vertNums || vertNums.length < vertexCount * 3) throw new Error("Vertex list truncated");
  const positions = new Float32Array(vertexCount * 3);
  for (let i = 0; i < vertexCount * 3; i++) positions[i] = Number(vertNums[i]);

  const afterVerts = vertSection.slice(faceCountMatch.index! + faceCountMatch[0].length);
  const faceNums = afterVerts.match(/\d+/g);
  if (!faceNums) throw new Error("Face list truncated");
  const indices = new Uint32Array(triangleCount * 3);
  let fi = 0;
  let cursor = 0;
  while (fi < triangleCount && cursor < faceNums.length) {
    const n = Number(faceNums[cursor++]);
    for (let k = 0; k < n; k++) indices[fi * 3 + k] = Number(faceNums[cursor++]);
    fi++;
  }

  const nrmBlock = meshInner.match(/MeshNormals\s*\{([\s\S]*?)\n\s*\}/);
  const normals = new Float32Array(vertexCount * 3);
  if (nrmBlock) {
    const nCount = nrmBlock[1].match(/^\s*(\d+);/);
    const nText = nCount ? nrmBlock[1].slice(nCount.index! + nCount[0].length) : nrmBlock[1];
    const nNums = nText.match(/-?\d+\.\d+|-?\d+/g) ?? [];
    for (let i = 0; i < Math.min(vertexCount * 3, nNums.length); i++) normals[i] = Number(nNums[i]);
  }

  const uvBlock = meshInner.match(/MeshTextureCoords\s*\{([\s\S]*?)\n\s*\}/);
  const uvs = new Float32Array(vertexCount * 2);
  if (uvBlock) {
    const uCount = uvBlock[1].match(/^\s*(\d+);/);
    const uText = uCount ? uvBlock[1].slice(uCount.index! + uCount[0].length) : uvBlock[1];
    const uNums = uText.match(/-?\d+\.\d+|-?\d+/g) ?? [];
    for (let i = 0; i < Math.min(vertexCount * 2, uNums.length); i++) uvs[i] = Number(uNums[i]);
  }

  const skinIndex = new Uint16Array(vertexCount * 4);
  const skinWeight = new Float32Array(vertexCount * 4);
  const filled = new Uint8Array(vertexCount);
  const weightBlocks = [...meshInner.matchAll(/SkinWeights\s*\{([\s\S]*?)\n\s*\}/g)];
  let boneCursor = 0;
  for (const block of weightBlocks) {
    const inner = block[1];
    const nameMatch = inner.match(/"([^"]+)"/);
    if (!nameMatch) continue;
    const nMatch = inner.match(/;\s*(\d+);/);
    const n = nMatch ? Number(nMatch[1]) : 0;
    if (n > 0) {
      const afterCount = inner.slice(inner.indexOf(nMatch![0]) + nMatch![0].length);
      const ints = afterCount.match(/-?\d+/g) ?? [];
      const floats = afterCount.match(/-?\d+\.\d+/g) ?? [];
      const idxs = ints.slice(0, n).map(Number);
      const ws = floats.slice(0, n).map(Number);
      for (let i = 0; i < n; i++) {
        const vi = idxs[i];
        const slot = filled[vi];
        if (slot < 4) {
          skinIndex[vi * 4 + slot] = boneCursor;
          skinWeight[vi * 4 + slot] = ws[i] ?? 0;
          filled[vi] = slot + 1;
        }
      }
    }
    boneCursor++;
  }
  for (let i = 0; i < vertexCount; i++) {
    const b = i * 4;
    const sum = skinWeight[b] + skinWeight[b + 1] + skinWeight[b + 2] + skinWeight[b + 3];
    if (sum > 1e-8) {
      skinWeight[b] /= sum;
      skinWeight[b + 1] /= sum;
      skinWeight[b + 2] /= sum;
      skinWeight[b + 3] /= sum;
    } else {
      skinWeight[b] = 1;
    }
  }

  void nums;
  void body;
  return { positions, normals, uvs, indices, skinIndex, skinWeight, textureName, vertexCount, triangleCount };
}

export function parseDirectXText(source: string): XMesh {
  if (!source.startsWith("xof ")) throw new Error("Not a DirectX .x file");
  const text = stripComments(source);
  const meshMatch = text.match(/Mesh\s*\{/);
  if (!meshMatch || meshMatch.index == null) throw new Error("No Mesh block in .x");
  const brace = text.indexOf("{", meshMatch.index);
  const { inner } = extractBalanced(text, brace);
  const mesh = parseMeshBlock(inner);
  const frameSrc = text.slice(0, meshMatch.index);
  const bones = parseFrames(frameSrc);
  return { ...mesh, bones };
}
