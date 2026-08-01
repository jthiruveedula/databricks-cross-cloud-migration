import React, { useMemo, useRef, useState, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import * as THREE from 'three';

// Same brand palette used elsewhere on the landing page (Hero.tsx rotating headline,
// BRAND_ICONS) -- kept in sync rather than re-deriving colors so the 3D scene reads as
// the same product, not a separate illustration. Positioned in the four corners rather
// than converging on a center hub -- the headline sits dead center, so (matching the
// established hero-video pattern of nodes living in the left/right clear zones) the ring
// traces the frame's perimeter and leaves the middle empty for text.
const NODES = [
  { key: 'aws', color: '#FF9900', position: [-3.3, 1.3, 0.5] },
  { key: 'azure', color: '#0078D4', position: [3.3, 1.3, -0.6] },
  { key: 'databricks', color: '#ff3621', position: [3.1, -1.3, 0.4] },
  { key: 'gcp', color: '#34A853', position: [-3.1, -1.3, -0.3] },
] as const;

function nodePosition(n: (typeof NODES)[number]) {
  return new THREE.Vector3(...n.position);
}

function GlowNode({ position, color, radius = 0.22 }: { position: THREE.Vector3; color: string; radius?: number }) {
  return (
    <group position={position}>
      <mesh>
        <icosahedronGeometry args={[radius, 1]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.6} roughness={0.35} metalness={0.2} />
      </mesh>
      {/* Cheap fake-bloom halo -- an additive-blended, larger transparent shell behind the
          solid node, instead of pulling in a full postprocessing bloom pipeline for one glow. */}
      <mesh scale={2.6}>
        <sphereGeometry args={[radius, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

function EnergyLine({ from, to, color, speed, offset }: { from: THREE.Vector3; to: THREE.Vector3; color: string; speed: number; offset: number }) {
  const particleRef = useRef<THREE.Mesh>(null);
  const reduced = useReducedMotionR3F();
  const points = useMemo(() => [from, to], [from, to]);

  useFrame(({ clock }) => {
    if (reduced || !particleRef.current) return;
    const t = (clock.elapsedTime * speed + offset) % 1;
    particleRef.current.position.lerpVectors(from, to, t);
    const mat = particleRef.current.material as THREE.MeshBasicMaterial;
    // fade in/out at each end so the particle doesn't pop at the node
    mat.opacity = Math.sin(t * Math.PI);
  });

  return (
    <group>
      <Line points={points} color={color} lineWidth={1} transparent opacity={0.28} />
      <mesh ref={particleRef} position={from}>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

// Module-level flag read by child components via a tiny hook -- avoids threading the
// prefers-reduced-motion prop through every mesh.
let reducedMotionFlag = false;
function useReducedMotionR3F() {
  return reducedMotionFlag;
}

function Scene({ isDark }: { isDark: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const { pointer } = useThree();
  const reduced = reducedMotionFlag;

  const nodePositions = useMemo(() => NODES.map((n) => nodePosition(n)), []);

  useFrame((_, delta) => {
    const group = groupRef.current;
    if (!group) return;
    if (reduced) return;
    // Idle drift + mouse parallax, damped toward target rather than snapping --
    // the same "orbit responds to the room" feel as the CSS hero orbs it replaces.
    const targetY = pointer.x * 0.25;
    const targetX = -pointer.y * 0.12;
    group.rotation.y += (targetY - group.rotation.y) * Math.min(1, delta * 2);
    group.rotation.x += (targetX - group.rotation.x) * Math.min(1, delta * 2);
  });

  return (
    <group ref={groupRef}>
      <ambientLight intensity={isDark ? 0.35 : 0.6} />
      <pointLight position={[0, 2, 5]} intensity={isDark ? 30 : 20} color="#ff8a3d" />
      {NODES.map((n, i) => {
        const next = nodePositions[(i + 1) % NODES.length];
        return (
          <React.Fragment key={n.key}>
            <GlowNode position={nodePositions[i]} color={n.color} />
            <EnergyLine from={nodePositions[i]} to={next} color={n.color} speed={0.1} offset={i / NODES.length} />
          </React.Fragment>
        );
      })}
    </group>
  );
}

export default function HeroScene3D({ isDark }: { isDark: boolean }) {
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
        <Scene isDark={isDark} />
      </Canvas>
    </div>
  );
}
