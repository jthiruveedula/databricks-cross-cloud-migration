import React, { useMemo, useRef, useState, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import * as THREE from 'three';

// Same brand palette used elsewhere on the landing page (Hero.tsx rotating headline,
// BRAND_ICONS) -- kept in sync rather than re-deriving colors so the 3D scene reads as
// the same product, not a separate illustration. Three SOURCE clouds sit in three corners;
// Databricks -- the migration TARGET -- sits in the fourth. Every source streams particles
// toward Databricks, not toward each other, so the motion literally depicts "migrate FROM
// these clouds INTO Databricks" instead of a decorative ring. Headline sits dead center, so
// (matching the established hero-video pattern) all four nodes live in the corners, leaving
// the middle clear for text.
const SOURCES = [
  { key: 'aws', color: '#FF9900', position: [-3.3, 1.3, 0.5] },
  { key: 'azure', color: '#0078D4', position: [3.3, 1.3, -0.6] },
  { key: 'gcp', color: '#34A853', position: [-3.1, -1.3, -0.3] },
] as const;

const TARGET = { key: 'databricks', color: '#ff3621', position: [3.1, -1.3, 0.4] } as const;

export type ActiveCloud = 'aws' | 'azure' | 'gcp' | null;

function vec(p: readonly [number, number, number]) {
  return new THREE.Vector3(...p);
}

function GlowNode({
  position,
  color,
  radius = 0.22,
  active,
}: {
  position: THREE.Vector3;
  color: string;
  radius?: number;
  active: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const reduced = reducedMotionFlag;

  useFrame(({ clock }, delta) => {
    // Active node (the one currently named in the headline, or Databricks receiving from
    // all three) breathes visibly brighter/larger; idle nodes settle to a quiet resting
    // state -- the pulse itself is the "this is the one migrating right now" signal.
    const targetScale = active ? 1.25 + Math.sin(clock.elapsedTime * 2.2) * 0.08 : 1;
    const targetHalo = active ? 3.2 : 2.4;
    if (meshRef.current) {
      const s = reduced ? targetScale : meshRef.current.scale.x + (targetScale - meshRef.current.scale.x) * Math.min(1, delta * 4);
      meshRef.current.scale.setScalar(s);
      const mat = meshRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = active ? 2.6 : 1.3;
    }
    if (haloRef.current) {
      const hs = reduced ? targetHalo : haloRef.current.scale.x + (targetHalo - haloRef.current.scale.x) * Math.min(1, delta * 4);
      haloRef.current.scale.setScalar(hs);
      const mat = haloRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = active ? 0.26 : 0.14;
    }
  });

  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[radius, 1]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.3} roughness={0.35} metalness={0.2} />
      </mesh>
      {/* Cheap fake-bloom halo -- an additive-blended, larger transparent shell behind the
          solid node, instead of pulling in a full postprocessing bloom pipeline for one glow. */}
      <mesh ref={haloRef} scale={2.4}>
        <sphereGeometry args={[radius, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.14} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

// 3 particles per stream at staggered offsets so it reads as a continuous flow of data
// rather than one dot commuting back and forth.
const STREAM_PARTICLES = 3;

function MigrationStream({
  from,
  to,
  color,
  active,
  laneOffset,
}: {
  from: THREE.Vector3;
  to: THREE.Vector3;
  color: string;
  active: boolean;
  laneOffset: number;
}) {
  const particleRefs = useRef<(THREE.Mesh | null)[]>([]);
  const points = useMemo(() => [from, to], [from, to]);

  useFrame(({ clock }) => {
    if (reducedMotionFlag) return;
    const speed = active ? 0.34 : 0.14; // active stream moves visibly faster -- "this is the one happening now"
    for (let i = 0; i < STREAM_PARTICLES; i++) {
      const mesh = particleRefs.current[i];
      if (!mesh) continue;
      const t = (clock.elapsedTime * speed + laneOffset + i / STREAM_PARTICLES) % 1;
      mesh.position.lerpVectors(from, to, t);
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = (active ? 0.95 : 0.45) * Math.sin(t * Math.PI);
    }
  });

  return (
    <group>
      <Line points={points} color={color} lineWidth={1} transparent opacity={active ? 0.4 : 0.16} />
      {Array.from({ length: STREAM_PARTICLES }).map((_, i) => (
        <mesh key={i} ref={(el) => { particleRefs.current[i] = el; }} position={from}>
          <sphereGeometry args={[active ? 0.07 : 0.05, 8, 8]} />
          <meshBasicMaterial color={color} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}

// Module-level flag read by child components via a tiny hook -- avoids threading
// prefers-reduced-motion through every mesh/frame callback.
let reducedMotionFlag = false;

function Scene({ isDark, activeCloud }: { isDark: boolean; activeCloud: ActiveCloud }) {
  const groupRef = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  const sourcePositions = useMemo(() => SOURCES.map((n) => vec(n.position)), []);
  const targetPosition = useMemo(() => vec(TARGET.position), []);

  useFrame((_, delta) => {
    const group = groupRef.current;
    if (!group || reducedMotionFlag) return;
    // Idle drift + mouse parallax, damped toward target rather than snapping -- the same
    // "orbit responds to the room" feel as the CSS hero orbs it replaces.
    const targetY = pointer.x * 0.25;
    const targetX = -pointer.y * 0.12;
    group.rotation.y += (targetY - group.rotation.y) * Math.min(1, delta * 2);
    group.rotation.x += (targetX - group.rotation.x) * Math.min(1, delta * 2);
  });

  return (
    <group ref={groupRef}>
      <ambientLight intensity={isDark ? 0.35 : 0.6} />
      <pointLight position={[0, 2, 5]} intensity={isDark ? 30 : 20} color="#ff8a3d" />
      {/* Databricks is always the receiving end, so it stays at its brighter "active" state
          regardless of which source cloud the headline currently names. */}
      <GlowNode position={targetPosition} color={TARGET.color} radius={0.26} active />
      {SOURCES.map((n, i) => {
        const isActive = activeCloud === n.key || activeCloud === null;
        return (
          <React.Fragment key={n.key}>
            <GlowNode position={sourcePositions[i]} color={n.color} active={isActive} />
            <MigrationStream
              from={sourcePositions[i]}
              to={targetPosition}
              color={n.color}
              active={isActive}
              laneOffset={i / SOURCES.length}
            />
          </React.Fragment>
        );
      })}
    </group>
  );
}

export default function HeroScene3D({ isDark, activeCloud }: { isDark: boolean; activeCloud: ActiveCloud }) {
  const [supported, setSupported] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      if (!gl) setSupported(false);
    } catch {
      setSupported(false);
    }
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    reducedMotionFlag = mq.matches;
    const onChange = () => {
      setReducedMotion(mq.matches);
      reducedMotionFlag = mq.matches;
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  if (!supported) return null;

  return (
    <div className="absolute inset-0 z-0" aria-hidden="true">
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [0, 0.4, 8], fov: 42 }}
        gl={{ alpha: true, antialias: true }}
        frameloop={reducedMotion ? 'demand' : 'always'}
      >
        <Scene isDark={isDark} activeCloud={activeCloud} />
      </Canvas>
    </div>
  );
}
