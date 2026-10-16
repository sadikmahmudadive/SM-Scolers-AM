export type SceneMode = "3d" | "static";

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Client-only. Static under prefers-reduced-motion or without WebGL; three.js is only loaded for "3d". */
export function detectSceneMode(): SceneMode {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return reduce || !webglAvailable() ? "static" : "3d";
}
