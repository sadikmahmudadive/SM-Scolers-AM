"use client";

import { useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import type { Group, MeshBasicMaterial } from "three";

const PULSE_MS = 600;

function Globe({ pulseKey }: { pulseKey: string | number }) {
  const group = useRef<Group>(null);
  const mat = useRef<MeshBasicMaterial>(null);
  const pulseStart = useRef<number | null>(null);
  const first = useRef(true);
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    pulseStart.current = performance.now();
    invalidate();
  }, [pulseKey, invalidate]);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    g.rotation.y += delta * 0.25;
    let scale = 1;
    if (pulseStart.current !== null) {
      const t = (performance.now() - pulseStart.current) / PULSE_MS;
      if (t >= 1) pulseStart.current = null;
      else scale = 1 + 0.25 * Math.sin(Math.PI * t);
    }
    g.scale.setScalar(scale);
    mat.current?.color.set(scale > 1.01 ? "#c7d0ff" : "#8b9cff");
    // Demand frameloop: keep the slow rotation going; the wrapper unmounts this canvas when the tab is hidden.
    invalidate();
  });

  return (
    <group ref={group}>
      <mesh>
        <sphereGeometry args={[1.2, 20, 14]} />
        <meshBasicMaterial ref={mat} wireframe color="#8b9cff" transparent opacity={0.7} />
      </mesh>
    </group>
  );
}

export default function PresenceGlobeScene({ pulseKey }: { pulseKey: string | number }) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      frameloop="demand"
      camera={{ position: [0, 0, 3.6], fov: 45 }}
      style={{ pointerEvents: "none" }}
    >
      <Globe pulseKey={pulseKey} />
    </Canvas>
  );
}
