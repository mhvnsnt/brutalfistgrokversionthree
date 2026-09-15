export type PreviewBone = {
  name: string;
  parent: number;
  matrix: number[];
};

export type PreviewMesh = {
  vertexCount: number;
  triangleCount: number;
  positions: number[];
  normals: number[];
  uvs: number[];
  indices: number[];
  skinIndex: number[];
  skinWeight: number[];
  bones: PreviewBone[];
  texture: string;
  sourceX: string;
};

export type AnimTrack = {
  r?: number[][];
  t?: number[][];
};

export type ClipJson = {
  clip: string;
  cat?: string;
  fps: number;
  duration: number;
  frames?: number;
  tracks: Record<string, AnimTrack>;
  x?: string;
  source?: string;
};

export type MocapManifest = {
  counts: Record<string, number>;
  clips: Array<{
    clip: string;
    slug?: string;
    cat: string;
    status: string;
    reason?: string;
    viewer?: string;
    frames?: number;
    duration?: number;
    x?: string;
  }>;
};
