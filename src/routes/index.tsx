import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { RingCanvas } from "@/components/ring-canvas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ClipJson, PreviewMesh } from "@/lib/native/x-mesh";

export const Route = createFileRoute("/")({ component: Home });

type Status = {
  character: string;
  policy: string;
  sourceGlb: string;
  mesh: {
    file: string;
    vertices: number;
    triangles: number;
    bones: number;
    xBytes: number;
    scale: number;
  };
  engine: {
    executableLoads: string;
    roster: string;
    path: string;
    installed: boolean;
  };
  mocap: Record<string, number>;
  bound: Array<{ engine: string; clip: string; frames?: number }>;
  clips: Array<{
    clip: string;
    cat?: string;
    status?: string;
    viewer?: string;
    source?: string;
  }>;
};

function Home() {
  const [status, setStatus] = useState<Status | null>(null);
  const [mesh, setMesh] = useState<PreviewMesh | null>(null);
  const [clip, setClip] = useState<ClipJson | null>(null);
  const [clipId, setClipId] = useState("idle");
  const [psx, setPsx] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/native/chara_bannon/status.json").then((r) => r.json()),
      fetch("/native/chara_bannon/preview.json").then((r) => r.json()),
    ])
      .then(([s, m]) => {
        if (cancelled) return;
        setStatus(s as Status);
        setMesh(m as PreviewMesh);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load Bannon .x");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const row = status?.clips.find((c) => c.clip === clipId);
    const path = row?.viewer ?? `clips/${clipId}.json`;
    let cancelled = false;
    fetch(`/native/chara_bannon/${path}`)
      .then((r) => {
        if (!r.ok) throw new Error(`clip ${clipId} missing`);
        return r.json();
      })
      .then((data: ClipJson) => {
        if (!cancelled) setClip(data);
      })
      .catch(() => {
        if (!cancelled) setClip(null);
      });
    return () => {
      cancelled = true;
    };
  }, [clipId, status]);

  const mocap = status?.mocap;
  const clipRows = status?.clips ?? [];

  const stats = useMemo(() => {
    if (!status) return [];
    return [
      ["GLB", "BANNON_rigged.glb"],
      [".x mesh", status.mesh.file],
      ["Triangles", status.mesh.triangles.toLocaleString()],
      ["Vertices", status.mesh.vertices.toLocaleString()],
      ["Bones", String(status.mesh.bones)],
      ["Scale", status.mesh.scale.toFixed(2)],
      ["FBX exported", String(mocap?.exported ?? 0)],
      ["Listed", String(mocap?.listed ?? 0)],
    ];
  }, [status, mocap]);

  return (
    <main className="relative min-h-dvh overflow-hidden bg-bg text-fg">
      <div className="absolute inset-0">
        {mesh ? (
          <RingCanvas
            mesh={mesh}
            textureUrl="/native/chara_bannon/bannon.png"
            clip={clip}
            psx={psx}
            playing={playing}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted">
            {error ?? "Loading BANNON_rigged → DirectX .x"}
          </div>
        )}
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 p-4 md:p-5">
        <div className="pointer-events-auto rounded-[var(--radius-md)] border border-border bg-bg/80 px-4 py-3 backdrop-blur-md">
          <p className="font-display text-xs uppercase tracking-[0.28em] text-muted">Brutal Fist</p>
          <h1 className="font-display text-3xl font-semibold uppercase leading-none tracking-wide">
            Bannon
          </h1>
          <p className="mt-1 max-w-xs text-sm text-muted">
            Real GLB converted to the DirectX .x slot Schwarzerblitz loads with getMesh.
          </p>
        </div>
        <div className="pointer-events-auto hidden flex-col items-end gap-2 sm:flex">
          <Badge>REAL_GLB_ONLY</Badge>
          <Badge>chara_bannon · roster 0</Badge>
        </div>
      </header>

      <aside className="pointer-events-none absolute bottom-28 left-4 z-10 hidden max-w-xs md:block">
        <div className="pointer-events-auto rounded-[var(--radius-md)] border border-border bg-bg/80 p-4 backdrop-blur-md">
          <p className="font-display text-xs uppercase tracking-[0.22em] text-muted">Native pipeline</p>
          <ul className="mt-3 space-y-1.5 text-sm">
            {stats.map(([k, v]) => (
              <li key={k} className="flex justify-between gap-6">
                <span className="text-subtle">{k}</span>
                <span className="font-mono text-fg">{v}</span>
              </li>
            ))}
          </ul>
          {status?.bound?.length ? (
            <div className="mt-3 border-t border-border pt-3">
              <p className="text-xs uppercase tracking-[0.18em] text-subtle">Engine binds</p>
              <ul className="mt-2 space-y-1 text-sm">
                {status.bound.map((b) => (
                  <li key={b.engine} className="flex justify-between gap-4">
                    <span className="text-muted">{b.engine}</span>
                    <span className="truncate text-fg">{b.clip}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </aside>

      <section className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-3 md:p-4">
        <div className="pointer-events-auto rounded-[var(--radius-md)] border border-border bg-bg/85 p-3 backdrop-blur-md">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? "Pause clip" : "Play clip"}
            >
              {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
              <span className="ml-2">{playing ? "Pause" : "Play"}</span>
            </Button>
            <Button variant="outline" onClick={() => setPsx((p) => !p)}>
              {psx ? "PSX 320×240" : "Full res"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setClipId("idle");
                setPlaying(true);
              }}
            >
              <RotateCcw className="size-4" />
              <span className="ml-2">Idle</span>
            </Button>
            <span className="ml-auto hidden text-xs uppercase tracking-[0.16em] text-subtle sm:inline">
              {clipId} · {clip?.source ?? clip?.cat ?? "rest pose"}
            </span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {clipRows.map((row) => {
              const active = row.clip === clipId;
              return (
                <button
                  key={row.clip}
                  type="button"
                  onClick={() => setClipId(row.clip)}
                  className={
                    "min-h-11 shrink-0 rounded-[var(--radius-sm)] border px-3 text-sm " +
                    (active
                      ? "border-accent bg-accent text-accent-fg"
                      : "border-border bg-surface text-fg")
                  }
                >
                  {row.clip}
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
