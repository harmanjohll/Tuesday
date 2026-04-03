import { useRef, useEffect } from "preact/hooks";

// Quantum-inspired particle system for Tuesday's visual presence
// Particles: quarks (RGB triplets), electrons (orbital), gluon connections
// States: idle, listening, thinking, speaking

const QUARK_COLORS = [
  [255, 80, 80],   // red
  [80, 200, 80],   // green
  [80, 120, 255],  // blue
];

const ELECTRON_COLOR = [140, 200, 255];
const GLUON_COLOR = [200, 180, 255];

function createQuarkTriplet(cx, cy, id) {
  const angle = Math.random() * Math.PI * 2;
  const dist = 30 + Math.random() * 60;
  const baseX = cx + Math.cos(angle) * dist;
  const baseY = cy + Math.sin(angle) * dist;
  return QUARK_COLORS.map((color, i) => ({
    type: "quark",
    tripletId: id,
    x: baseX + Math.cos((i * Math.PI * 2) / 3) * 8,
    y: baseY + Math.sin((i * Math.PI * 2) / 3) * 8,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    color,
    size: 2.5 + Math.random() * 1.5,
    phase: Math.random() * Math.PI * 2,
    orbitSpeed: 0.008 + Math.random() * 0.008,
    orbitRadius: 6 + Math.random() * 4,
    baseX,
    baseY,
  }));
}

function createElectron(cx, cy) {
  const angle = Math.random() * Math.PI * 2;
  const orbit = 60 + Math.random() * 100;
  return {
    type: "electron",
    x: cx + Math.cos(angle) * orbit,
    y: cy + Math.sin(angle) * orbit,
    vx: 0,
    vy: 0,
    color: ELECTRON_COLOR,
    size: 2 + Math.random() * 1.5,
    phase: angle,
    orbitSpeed: 0.003 + Math.random() * 0.006,
    orbitRadius: orbit,
    trail: [],
  };
}

function initParticles(cx, cy) {
  const particles = [];

  // 6 quark triplets
  for (let i = 0; i < 6; i++) {
    particles.push(...createQuarkTriplet(cx, cy, i));
  }

  // 12 electrons
  for (let i = 0; i < 12; i++) {
    particles.push(createElectron(cx, cy));
  }

  return particles;
}

// State behavior parameters
const STATE_CONFIG = {
  idle: {
    speed: 1,
    contraction: 1,
    glow: 0.15,
    colorIntensity: 0.6,
    waveAmplitude: 0,
    entanglement: 0,
  },
  listening: {
    speed: 1.5,
    contraction: 0.5,
    glow: 0.35,
    colorIntensity: 1.0,
    waveAmplitude: 0,
    entanglement: 0,
  },
  thinking: {
    speed: 3,
    contraction: 0.7,
    glow: 0.5,
    colorIntensity: 0.9,
    waveAmplitude: 0,
    entanglement: 1,
  },
  speaking: {
    speed: 1.8,
    contraction: 1.3,
    glow: 0.4,
    colorIntensity: 0.85,
    waveAmplitude: 1,
    entanglement: 0,
  },
};

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const particlesRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const currentConfigRef = useRef({ ...STATE_CONFIG.idle });
  const wavesRef = useRef([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let width, height, cx, cy;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.parentElement.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx = width / 2;
      cy = height / 2;

      if (!particlesRef.current) {
        particlesRef.current = initParticles(cx, cy);
      }
    };

    resize();
    window.addEventListener("resize", resize);

    const lerp = (a, b, t) => a + (b - a) * t;

    const animate = () => {
      timeRef.current += 1;
      const t = timeRef.current;
      const target = STATE_CONFIG[state] || STATE_CONFIG.idle;
      const cfg = currentConfigRef.current;

      // Smooth interpolation toward target state
      for (const key in target) {
        cfg[key] = lerp(cfg[key], target[key], 0.04);
      }

      ctx.clearRect(0, 0, width, height);

      // Draw probability cloud (gaussian glow)
      const cloudRadius = 120 * cfg.contraction;
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, cloudRadius);
      gradient.addColorStop(0, `rgba(74, 168, 255, ${cfg.glow * 0.3})`);
      gradient.addColorStop(0.4, `rgba(74, 168, 255, ${cfg.glow * 0.15})`);
      gradient.addColorStop(1, "rgba(74, 168, 255, 0)");
      ctx.beginPath();
      ctx.arc(cx, cy, cloudRadius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();

      // Emission waves (speaking state)
      const waves = wavesRef.current;
      if (cfg.waveAmplitude > 0.3) {
        if (t % 30 === 0) {
          waves.push({ radius: 20, opacity: 0.3 });
        }
      }
      for (let i = waves.length - 1; i >= 0; i--) {
        const w = waves[i];
        w.radius += 2;
        w.opacity -= 0.004;
        if (w.opacity <= 0) {
          waves.splice(i, 1);
          continue;
        }
        ctx.beginPath();
        ctx.arc(cx, cy, w.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(74, 168, 255, ${w.opacity})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      const particles = particlesRef.current;
      if (!particles) {
        frameRef.current = requestAnimationFrame(animate);
        return;
      }

      // Group quarks by triplet for gluon lines
      const triplets = {};

      for (const p of particles) {
        // Update position
        p.phase += p.orbitSpeed * cfg.speed;

        if (p.type === "quark") {
          // Quarks orbit their triplet center, which itself drifts
          const contractionForce = cfg.contraction < 1 ? 0.02 : -0.005;
          const dx = cx - p.baseX;
          const dy = cy - p.baseY;
          p.baseX += dx * contractionForce;
          p.baseY += dy * contractionForce;

          // Gentle drift
          p.baseX += Math.sin(t * 0.005 + p.phase) * 0.15;
          p.baseY += Math.cos(t * 0.007 + p.phase) * 0.15;

          p.x = p.baseX + Math.cos(p.phase) * p.orbitRadius;
          p.y = p.baseY + Math.sin(p.phase) * p.orbitRadius;

          if (!triplets[p.tripletId]) triplets[p.tripletId] = [];
          triplets[p.tripletId].push(p);
        } else if (p.type === "electron") {
          // Electrons orbit the center
          const targetRadius = p.orbitRadius * cfg.contraction;
          const currentRadius = Math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2);
          const adjustedRadius = lerp(currentRadius, targetRadius, 0.02);

          p.x = cx + Math.cos(p.phase) * adjustedRadius;
          p.y = cy + Math.sin(p.phase) * adjustedRadius;

          // Trail
          p.trail.push({ x: p.x, y: p.y });
          if (p.trail.length > 8) p.trail.shift();
        }

        // Entanglement effect (thinking): mirror particles
        if (cfg.entanglement > 0.5 && p.type === "electron") {
          const flicker = Math.sin(t * 0.2 + p.phase * 3) > 0;
          if (flicker) {
            ctx.beginPath();
            ctx.arc(cx * 2 - p.x, cy * 2 - p.y, p.size * 0.7, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${p.color.join(",")}, ${0.2 * cfg.entanglement})`;
            ctx.fill();
          }
        }
      }

      // Draw gluon connections (faint lines between quarks in each triplet)
      for (const id in triplets) {
        const tri = triplets[id];
        if (tri.length < 2) continue;
        ctx.beginPath();
        ctx.moveTo(tri[0].x, tri[0].y);
        for (let i = 1; i < tri.length; i++) {
          ctx.lineTo(tri[i].x, tri[i].y);
        }
        ctx.closePath();
        ctx.strokeStyle = `rgba(${GLUON_COLOR.join(",")}, ${0.12 * cfg.colorIntensity})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      // Draw electron trails
      for (const p of particles) {
        if (p.type === "electron" && p.trail.length > 1) {
          ctx.beginPath();
          ctx.moveTo(p.trail[0].x, p.trail[0].y);
          for (let i = 1; i < p.trail.length; i++) {
            ctx.lineTo(p.trail[i].x, p.trail[i].y);
          }
          ctx.strokeStyle = `rgba(${p.color.join(",")}, ${0.1 * cfg.colorIntensity})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      // Draw particles
      for (const p of particles) {
        const alpha = cfg.colorIntensity * (p.type === "quark" ? 0.9 : 0.7);
        const glow = cfg.glow * 12;

        // Glow
        if (glow > 2) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size + glow, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${p.color.join(",")}, ${alpha * 0.15})`;
          ctx.fill();
        }

        // Core
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color.join(",")}, ${alpha})`;
        ctx.fill();
      }

      frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [state]);

  return (
    <canvas
      ref={canvasRef}
      class="quantum-field"
      aria-hidden="true"
    />
  );
}
