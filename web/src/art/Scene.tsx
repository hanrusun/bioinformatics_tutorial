import { useEffect, useState } from 'preact/hooks';
import type { Stage } from '../types';
import { PatientScene, type SceneProps } from './PatientScene';

export interface ArtManifest {
  scene?: Partial<Record<Stage | 'default', string>>;
  overlays?: Record<string, string>;
  portrait?: string;
}

const cache = new Map<string, Promise<ArtManifest>>();

export function loadManifest(art: string): Promise<ArtManifest> {
  if (!cache.has(art)) {
    cache.set(
      art,
      fetch(`/art/${art}/manifest.json`)
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({})),
    );
  }
  return cache.get(art)!;
}

/** Resolve which pieces of art come from the manifest (custom files) and
 * which fall back to the built-in SVG. Exported for tests. */
export function resolveArt(manifest: ArtManifest, art: string, stage: Stage, overlays: string[]) {
  const base = manifest.scene?.[stage] || manifest.scene?.default || '';
  const custom = overlays.filter((k) => manifest.overlays?.[k]);
  return {
    baseImage: base ? `/art/${art}/${base}` : null,
    customOverlays: custom.map((k) => ({ key: k, src: `/art/${art}/${manifest.overlays![k]}` })),
    builtInOverlays: overlays.filter((k) => !manifest.overlays?.[k]),
  };
}

/** Patient scene: built-in SVG, or custom images from public/art/<art>/manifest.json. */
export function Scene(props: SceneProps) {
  const [manifest, setManifest] = useState<ArtManifest>({});
  useEffect(() => {
    let live = true;
    loadManifest(props.art).then((m) => live && setManifest(m));
    return () => {
      live = false;
    };
  }, [props.art]);

  const { baseImage, customOverlays, builtInOverlays } = resolveArt(manifest, props.art, props.stage, props.overlays);
  return (
    <div class="scene-wrap">
      {baseImage ? (
        <img class="scene scene--custom" src={baseImage} alt={`The patient (${props.stage})`} />
      ) : (
        <PatientScene {...props} overlays={builtInOverlays} />
      )}
      {customOverlays.map((o) => (
        <img key={o.key} class="scene-overlay" src={o.src} alt="" />
      ))}
    </div>
  );
}
