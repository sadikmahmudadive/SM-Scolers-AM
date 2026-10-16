"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Points, PointMaterial } from "@react-three/drei";
import type { Points as ThreePoints } from "three";

function Field() {
  const ref = useRef<ThreePoints>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(1500 * 3);
    for (let i = 0; i < arr.length; i++) arr[i] = (Math.random() - 0.5) * 8;
    return arr;
  }, []);
  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += delta * 0.04;
    ref.current.rotation.x += delta * 0.015;
  });
  return (
    <Points ref={ref} positions={positions} stride={3} frustumCulled={false}>
      <PointMaterial transparent color="#8b9cff" size={0.025} sizeAttenuation depthWrite={false} opacity={0.7} />
    </Points>
  );
}

export default function LoginBackdropScene() {
  return (
    <Canvas dpr={[1, 1.5]} camera={{ position: [0, 0, 4], fov: 60 }} style={{ pointerEvents: "none" }}>
      <Field />
    </Canvas>
  );
}
