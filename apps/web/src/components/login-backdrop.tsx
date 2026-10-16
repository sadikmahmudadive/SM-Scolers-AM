"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// three.js is only downloaded when the 3D scene is actually going to render.
const Scene = dynamic(() => import("./login-backdrop-scene"), { ssr: false });

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function LoginBackdrop() {
  const [mode, setMode] = useState<"pending" | "3d" | "static">("pending");

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setMode(reduce || !webglAvailable() ? "static" : "3d");
  }, []);

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-100 via-background to-sky-100 dark:from-indigo-950 dark:via-background dark:to-slate-900" />
      {mode === "3d" && <Scene />}
    </div>
  );
}
