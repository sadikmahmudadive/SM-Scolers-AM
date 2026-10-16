"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { detectSceneMode } from "@/lib/scene-mode";

// three.js is only downloaded in "3d" mode.
const Scene = dynamic(() => import("./presence-globe-scene"), { ssr: false });

function StaticGlobe() {
  return (
    <svg viewBox="0 0 100 100" className="h-full w-full text-indigo-400" fill="none" stroke="currentColor" strokeWidth="1">
      <circle cx="50" cy="50" r="38" />
      <ellipse cx="50" cy="50" rx="16" ry="38" />
      <ellipse cx="50" cy="50" rx="30" ry="38" />
      <path d="M12 50h76M18 30h64M18 70h64" />
    </svg>
  );
}

export function PresenceGlobe({ pulseKey }: { pulseKey: string | number }) {
  const [mode, setMode] = useState<"pending" | "3d" | "static">("pending");
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setMode(detectSceneMode());
    const onVis = () => setHidden(document.hidden);
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  return (
    <div aria-hidden="true" className="pointer-events-none h-[200px] w-[200px] shrink-0">
      {mode === "3d" && !hidden ? <Scene pulseKey={pulseKey} /> : mode === "pending" ? null : <StaticGlobe />}
    </div>
  );
}
