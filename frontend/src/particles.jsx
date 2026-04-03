import { useRef, useEffect } from "preact/hooks";

// Tuesday's visual presence: an ethereal quantum cloud
// A breathing, luminous nebula of stardust and electron haze
// Muted tones, soft glow, organic pulsing

// Muted quark colours (dusty, not saturated)
const QUARK_COLORS = [
  [180, 100, 100],  // dusty rose (red charge)
  [100, 170, 130],  // sage (green charge)
  [100, 130, 200],  // steel blue (blue charge)
];

const ANTIQUARK_COLORS = [
  [100, 170, 170],  // muted cyan
  [170, 100, 170],  // muted magenta
  [170, 170, 100],  // muted yellow
];

function gaussRandom(mean = 0, std = 1) {
  const u1 = Math.random();
  const u2 = Math.random();
  return mean + std * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function createDustParticle(cx, cy) {
  const r = Math.abs(gaussRandom(0, 80));
  const angle = Math.random() * Math.PI * 2;
  const temp = Math.random();

  // Colour palette: warm cream → cool lavender → pale blue
  let color;
  if (temp < 0.3) {
    color = [190 + Math.random() * 30, 180 + Math.random() * 25, 200 + Math.random() * 20]; // lavender
  } else if (temp < 0.6) {
    color = [200 + Math.random() * 25, 195 + Math.random() * 20, 210 + Math.random() * 15]; // warm cream
  } else {
    color = [150 + Math.random() * 30, 170 + Math.random() * 30, 220 + Math.random() * 20]; // pale blue
  }

  return {
    type: "dust",
    x: cx + Math.cos(angle) * r,
    y: cy + Math.sin(angle) * r,
    phase: Math.random() * Math.PI * 2,
    phaseSpeed: (0.0005 + Math.random() * 0.002) * (Math.random() > 0.5 ? 1 : -1),
    radius: r,
    color,
    coreSize: 0.3 + Math.random() * 0.8,
    glowSize: 4 + Math.random() * 10,
    opacity: 0.04 + Math.random() * 0.12,
    posUncertainty: 1 + Math.random() * 3,
    tunnelProb: 0.0002 + Math.random() * 0.0005,
    // Each particle has its own breathing phase offset
    breathOffset: Math.random() * Math.PI * 2,
  };
}

function createElectronParticle(cx, cy, shell) {
  const r = (shell * 25) + Math.abs(gaussRandom(0, shell * 10));
  const angle = Math.random() * Math.PI * 2;
  const warmth = 1 - (shell - 1) * 0.12;

  return {
    type: "electron",
    x: cx + Math.cos(angle) * r,
    y: cy + Math.sin(angle) * r,
    phase: Math.random() * Math.PI * 2,
    phaseSpeed: (0.001 + Math.random() * 0.003) * (Math.random() > 0.5 ? 1 : -1),
    radius: r,
    shell,
    color: [140 + 30 * warmth, 150 + 30 * warmth, 220 + 20 * warmth], // soft lavender-blue
    coreSize: 0.5 + Math.random() * 1.0,
    glowSize: 6 + Math.random() * 14,
    opacity: 0.06 + Math.random() * 0.15,
    posUncertainty: 1.5 + Math.random() * 3,
    tunnelProb: 0.0003 + Math.random() * 0.0007,
    ghostPhase: Math.random() * Math.PI * 2,
    ghostRadius: r * (0.6 + Math.random() * 0.8),
    breathOffset: Math.random() * Math.PI * 2,
  };
}

function createQuarkParticle(cx, cy, tripletId, colorIdx) {
  const angle = (tripletId * 0.618 * Math.PI * 2) + Math.random() * 0.5;
  const dist = 10 + Math.random() * 45;
  const bx = cx + Math.cos(angle) * dist;
  const by = cy + Math.sin(angle) * dist;
  const orbAngle = (colorIdx * Math.PI * 2) / 3;

  return {
    type: "quark",
    tripletId,
    x: bx + Math.cos(orbAngle) * 4,
    y: by + Math.sin(orbAngle) * 4,
    baseX: bx,
    baseY: by,
    phase: Math.random() * Math.PI * 2,
    phaseSpeed: 0.008 + Math.random() * 0.006,
    color: QUARK_COLORS[colorIdx],
    coreSize: 1.0 + Math.random() * 0.8,
    glowSize: 8 + Math.random() * 12,
    opacity: 0.15 + Math.random() * 0.2,
    confinement: 4 + Math.random() * 3,
    breathOffset: Math.random() * Math.PI * 2,
  };
}

function initParticles(cx, cy) {
  const particles = [];

  // ~280 dust particles (the nebula)
  for (let i = 0; i < 280; i++) {
    particles.push(createDustParticle(cx, cy));
  }

  // ~50 electron cloud particles across 4 shells
  for (let shell = 1; shell <= 4; shell++) {
    const count = shell === 1 ? 8 : shell === 2 ? 14 : shell === 3 ? 16 : 12;
    for (let i = 0; i < count; i++) {
      particles.push(createElectronParticle(cx, cy, shell));
    }
  }

  // 8 quark triplets (subtle clusters in the cloud)
  for (let i = 0; i < 8; i++) {
    for (let c = 0; c < 3; c++) {
      particles.push(createQuarkParticle(cx, cy, i, c));
    }
  }

  return particles;
}

// Pulse rhythm parameters per state
const PULSE_CONFIG = {
  idle:      { period: 240, depth: 0.08, irregularity: 0 },     // ~4s gentle breath
  listening: { period: 120, depth: 0.15, irregularity: 0 },     // ~2s deeper breath
  thinking:  { period: 30,  depth: 0.12, irregularity: 0.5 },   // ~0.5s rapid flutter
  speaking:  { period: 90,  depth: 0.10, irregularity: 0 },     // ~1.5s rhythmic
};

const STATE_CONFIG = {
  idle: {
    speed: 1,
    contraction: 1,
    glow: 0.2,
    colorIntensity: 0.45,
    uncertainty: 1.5,
    tunneling: 0.8,
    superposition: 0.5,
    decoherence: 0,
    fluctuation: 0.15,
  },
  listening: {
    speed: 1.3,
    contraction: 0.4,
    glow: 0.45,
    colorIntensity: 0.75,
    uncertainty: 0.4,
    tunneling: 0.15,
    superposition: 0.08,
    decoherence: 1.0,
    fluctuation: 0.05,
  },
  thinking: {
    speed: 2.2,
    contraction: 0.6,
    glow: 0.55,
    colorIntensity: 0.7,
    uncertainty: 2.0,
    tunneling: 2.5,
    superposition: 0.9,
    decoherence: 0,
    fluctuation: 0.6,
  },
  speaking: {
    speed: 1.5,
    contraction: 1.15,
    glow: 0.4,
    colorIntensity: 0.6,
    uncertainty: 0.8,
    tunneling: 0.4,
    superposition: 0.25,
    decoherence: 0.4,
    fluctuation: 0.1,
  },
};

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const particlesRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const cfgRef = useRef({ ...STATE_CONFIG.idle });
  const pulseRef = useRef({ ...PULSE_CONFIG.idle });
  const firefliesRef = useRef([]);

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
      const targetPulse = PULSE_CONFIG[state] || PULSE_CONFIG.idle;
      const cfg = cfgRef.current;
      const pulse = pulseRef.current;

      // Smooth transitions
      for (const key in target) cfg[key] = lerp(cfg[key], target[key], 0.025);
      for (const key in targetPulse) pulse[key] = lerp(pulse[key], targetPulse[key], 0.03);

      // Global heartbeat pulse
      const irregular = pulse.irregularity > 0 ? Math.sin(t * 0.13) * pulse.irregularity : 0;
      const heartbeat = Math.sin((t / pulse.period) * Math.PI * 2 + irregular) * pulse.depth;

      // Clean canvas each frame — no trails, no streaks
      ctx.clearRect(0, 0, width, height);

      const particles = particlesRef.current;
      if (!particles) {
        frameRef.current = requestAnimationFrame(animate);
        return;
      }

      // --- Breathing cloud layers ---
      const breathPhase = Math.sin(t * 0.008) * 0.15 + 1; // slow scale oscillation
      const cloudLayers = [
        { r: 50, color: "140, 150, 200", alpha: 0.04 },
        { r: 90, color: "120, 140, 210", alpha: 0.03 },
        { r: 140, color: "160, 140, 190", alpha: 0.02 },
        { r: 200, color: "130, 130, 180", alpha: 0.015 },
      ];

      for (const layer of cloudLayers) {
        const r = layer.r * cfg.contraction * breathPhase;
        const a = layer.alpha * (cfg.glow / 0.2) * (1 + heartbeat);
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        grad.addColorStop(0, `rgba(${layer.color}, ${a})`);
        grad.addColorStop(0.5, `rgba(${layer.color}, ${a * 0.4})`);
        grad.addColorStop(1, `rgba(${layer.color}, 0)`);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // --- Firefly blinks (vacuum fluctuations, softened) ---
      const ff = firefliesRef.current;
      if (cfg.fluctuation > 0.08 && Math.random() < cfg.fluctuation * 0.02) {
        const angle = Math.random() * Math.PI * 2;
        const dist = 15 + Math.random() * 90;
        const colorIdx = Math.floor(Math.random() * 3);
        ff.push({
          x: cx + Math.cos(angle) * dist,
          y: cy + Math.sin(angle) * dist,
          life: 50 + Math.random() * 40,
          maxLife: 50 + Math.random() * 40,
          color: Math.random() > 0.5 ? QUARK_COLORS[colorIdx] : ANTIQUARK_COLORS[colorIdx],
          size: 2 + Math.random() * 4,
        });
      }

      for (let i = ff.length - 1; i >= 0; i--) {
        const f = ff[i];
        f.life--;
        if (f.life <= 0) { ff.splice(i, 1); continue; }
        const progress = 1 - f.life / f.maxLife;
        // Soft fade in/out (firefly pulse)
        const alpha = Math.sin(progress * Math.PI) * 0.15;
        const grad = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, f.size);
        grad.addColorStop(0, `rgba(${f.color.join(",")}, ${alpha})`);
        grad.addColorStop(1, `rgba(${f.color.join(",")}, 0)`);
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.size, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // --- Update and draw particles ---
      for (const p of particles) {
        p.phase += p.phaseSpeed * cfg.speed;

        // Per-particle breathing offset
        const particlePulse = heartbeat * 0.5 + Math.sin(t * 0.01 + p.breathOffset) * 0.03;

        if (p.type === "quark") {
          // Quarks drift gently toward/away from center
          const driftForce = cfg.contraction < 1 ? 0.01 : -0.002;
          p.baseX += (cx - p.baseX) * driftForce;
          p.baseY += (cy - p.baseY) * driftForce;
          p.baseX += Math.sin(t * 0.002 + p.phase) * 0.08;
          p.baseY += Math.cos(t * 0.003 + p.phase) * 0.08;
          p.x = p.baseX + Math.cos(p.phase) * p.confinement;
          p.y = p.baseY + Math.sin(p.phase) * p.confinement;
        } else {
          // Dust and electrons: orbital drift with uncertainty jitter
          const jitter = cfg.uncertainty * p.posUncertainty;
          const jx = gaussRandom(0, jitter);
          const jy = gaussRandom(0, jitter);
          const targetR = p.radius * cfg.contraction;
          p.radius = lerp(p.radius, targetR, 0.008);
          p.x = cx + Math.cos(p.phase) * p.radius + jx;
          p.y = cy + Math.sin(p.phase) * p.radius + jy;

          // Tunneling
          if (Math.random() < (p.tunnelProb || 0) * cfg.tunneling) {
            p.radius = Math.abs(gaussRandom(0, 80)) * cfg.contraction;
          }
        }

        // Draw: glow halo first, then tiny core
        const alpha = p.opacity * cfg.colorIntensity * (1 + particlePulse);
        const [r, g, b] = p.color;

        // Glow (soft radial gradient)
        const glowR = p.glowSize * (1 + particlePulse * 2);
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowR);
        grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha * 0.4})`);
        grad.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${alpha * 0.12})`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        ctx.beginPath();
        ctx.arc(p.x, p.y, glowR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Core (tiny bright point)
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.coreSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${Math.min(alpha * 1.5, 0.6)})`;
        ctx.fill();

        // Superposition ghost for electrons
        if (p.type === "electron" && cfg.superposition > 0.1) {
          p.ghostPhase += (p.phaseSpeed || 0) * cfg.speed * 0.6;
          const gr = (p.ghostRadius || p.radius) * cfg.contraction;
          const gx = cx + Math.cos(p.ghostPhase) * gr + gaussRandom(0, cfg.uncertainty);
          const gy = cy + Math.sin(p.ghostPhase) * gr + gaussRandom(0, cfg.uncertainty);
          const ghostAlpha = alpha * cfg.superposition * 0.2;
          const ghostGrad = ctx.createRadialGradient(gx, gy, 0, gx, gy, p.glowSize * 0.6);
          ghostGrad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${ghostAlpha})`);
          ghostGrad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
          ctx.beginPath();
          ctx.arc(gx, gy, p.glowSize * 0.6, 0, Math.PI * 2);
          ctx.fillStyle = ghostGrad;
          ctx.fill();
        }
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
