import { useRef, useEffect } from "preact/hooks";

// Quantum field visualization for Tuesday
// Dense stardust cloud using real QM-inspired distributions:
// - Hydrogen-like orbital probability densities (1s, 2p, 3d shells)
// - Quark triplets with color confinement (can't escape ~1fm apart)
// - Quantum tunneling: particles occasionally jump through barriers
// - Heisenberg uncertainty: position blurs when momentum is known, and vice versa
// - Superposition: particles exist in multiple positions simultaneously (ghost images)
// - Decoherence: superposition collapses when "observed" (listening state)

// QCD quark colors
const QUARK_COLORS = [
  [255, 70, 70],   // red
  [70, 210, 70],   // green
  [70, 110, 255],  // blue
];

// Pastel variants for anti-quarks / virtual pairs
const ANTIQUARK_COLORS = [
  [70, 210, 210],  // cyan (anti-red)
  [210, 70, 210],  // magenta (anti-green)
  [210, 210, 70],  // yellow (anti-blue)
];

// Box-Muller transform for gaussian random numbers
function gaussRandom(mean = 0, std = 1) {
  const u1 = Math.random();
  const u2 = Math.random();
  return mean + std * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

// Hydrogen-like radial probability: r^2 * exp(-2r/n) for shell n
function orbitalRadius(shell) {
  // Sample from radial distribution using rejection sampling approximation
  const n = shell;
  const peak = n * n; // most probable radius scales as n^2
  return Math.abs(gaussRandom(peak, peak * 0.4));
}

// Spherical harmonic-inspired angular distribution
function orbitalAngle(l, m, phase) {
  // l = angular momentum quantum number, m = magnetic quantum number
  // Creates lobed patterns for p, d orbitals
  if (l === 0) return Math.random() * Math.PI * 2; // s orbital: spherical
  // p orbital: figure-8 lobes
  const baseAngle = (m * Math.PI * 2) / (2 * l + 1);
  return baseAngle + gaussRandom(0, 0.3) + phase;
}

function createCloudParticle(cx, cy, shell, type) {
  const n = shell; // principal quantum number
  const l = Math.floor(Math.random() * n); // angular momentum: 0 to n-1
  const m = Math.floor(Math.random() * (2 * l + 1)) - l; // magnetic: -l to +l
  const spin = Math.random() > 0.5 ? 0.5 : -0.5;

  const r = orbitalRadius(shell) * 2.5; // scale factor for display
  const angle = orbitalAngle(l, m, Math.random() * Math.PI * 2);

  // Color based on type and shell
  let color;
  if (type === "electron") {
    // Electrons: blue-white, cooler in outer shells
    const warmth = 1 - (shell - 1) * 0.15;
    color = [100 + 40 * warmth, 170 + 30 * warmth, 255];
  } else if (type === "stardust") {
    // Ambient stardust: very faint, warm white to cool blue
    const temp = Math.random();
    color = temp > 0.5
      ? [200 + Math.random() * 55, 210 + Math.random() * 45, 240 + Math.random() * 15]
      : [180 + Math.random() * 40, 160 + Math.random() * 40, 220 + Math.random() * 35];
  } else {
    color = [140, 200, 255];
  }

  return {
    type,
    x: cx + Math.cos(angle) * r,
    y: cy + Math.sin(angle) * r,
    homeX: cx,
    homeY: cy,
    shell: n,
    l,
    m,
    spin,
    phase: Math.random() * Math.PI * 2,
    phaseSpeed: (0.001 + Math.random() * 0.004) * (spin > 0 ? 1 : -1),
    radius: r,
    angle,
    color,
    size: type === "stardust" ? 0.5 + Math.random() * 1.0 : 1.0 + Math.random() * 1.5,
    opacity: type === "stardust" ? 0.1 + Math.random() * 0.25 : 0.3 + Math.random() * 0.4,
    // Uncertainty principle: momentum uncertainty inversely proportional to position certainty
    posUncertainty: 0.5 + Math.random() * 2,
    momUncertainty: 0,
    // Tunneling probability
    tunnelProb: 0.0003 + Math.random() * 0.0007,
    // Superposition ghost
    ghostPhase: Math.random() * Math.PI * 2,
    ghostRadius: r * (0.7 + Math.random() * 0.6),
  };
}

function createQuarkTriplet(cx, cy, id) {
  const angle = Math.random() * Math.PI * 2;
  const dist = 15 + Math.random() * 50;
  const bx = cx + Math.cos(angle) * dist;
  const by = cy + Math.sin(angle) * dist;

  // Confinement radius ~1fm (scaled up for display)
  const confinement = 5 + Math.random() * 3;

  return QUARK_COLORS.map((color, i) => ({
    type: "quark",
    tripletId: id,
    x: bx + Math.cos((i * Math.PI * 2) / 3) * confinement,
    y: by + Math.sin((i * Math.PI * 2) / 3) * confinement,
    baseX: bx,
    baseY: by,
    homeX: cx,
    homeY: cy,
    color,
    size: 1.5 + Math.random() * 1.0,
    opacity: 0.6 + Math.random() * 0.3,
    phase: Math.random() * Math.PI * 2,
    phaseSpeed: 0.015 + Math.random() * 0.01,
    confinement,
    // Color charge oscillation (gluon exchange)
    colorPhase: Math.random() * Math.PI * 2,
    colorSpeed: 0.005 + Math.random() * 0.008,
  }));
}

function initParticles(cx, cy) {
  const particles = [];

  // Dense stardust cloud: ~200 ambient particles in gaussian distribution
  for (let i = 0; i < 200; i++) {
    const shell = 1 + Math.floor(Math.random() * 4); // shells 1-4
    particles.push(createCloudParticle(cx, cy, shell, "stardust"));
  }

  // Electron cloud: ~40 electrons across shells
  for (let shell = 1; shell <= 4; shell++) {
    const count = shell === 1 ? 6 : shell === 2 ? 12 : shell === 3 ? 14 : 8;
    for (let i = 0; i < count; i++) {
      particles.push(createCloudParticle(cx, cy, shell, "electron"));
    }
  }

  // 10 quark triplets (confined)
  for (let i = 0; i < 10; i++) {
    particles.push(...createQuarkTriplet(cx, cy, i));
  }

  return particles;
}

// State parameters
const STATE_CONFIG = {
  idle: {
    speed: 1,
    contraction: 1,
    glow: 0.12,
    colorIntensity: 0.5,
    uncertainty: 1.0,   // Heisenberg: high position uncertainty = spread out
    tunneling: 1.0,
    superposition: 0.6, // ghost images visible
    decoherence: 0,     // no wavefunction collapse
    fluctuation: 0.3,   // vacuum fluctuations (virtual pairs)
  },
  listening: {
    speed: 1.2,
    contraction: 0.45,
    glow: 0.3,
    colorIntensity: 0.9,
    uncertainty: 0.3,   // position becomes certain (collapse)
    tunneling: 0.2,
    superposition: 0.1, // superposition collapses - being "observed"
    decoherence: 1.0,   // full decoherence
    fluctuation: 0.1,
  },
  thinking: {
    speed: 2.5,
    contraction: 0.65,
    glow: 0.45,
    colorIntensity: 0.85,
    uncertainty: 1.5,   // high uncertainty = exploring possibilities
    tunneling: 2.0,     // lots of tunneling = exploring solution space
    superposition: 1.0, // maximum superposition = considering all states
    decoherence: 0,
    fluctuation: 0.8,   // heavy vacuum fluctuations
  },
  speaking: {
    speed: 1.6,
    contraction: 1.2,
    glow: 0.35,
    colorIntensity: 0.75,
    uncertainty: 0.7,
    tunneling: 0.5,
    superposition: 0.3,
    decoherence: 0.5,
    fluctuation: 0.2,
  },
};

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const particlesRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const cfgRef = useRef({ ...STATE_CONFIG.idle });
  const virtualPairsRef = useRef([]);

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
      const cfg = cfgRef.current;

      // Smooth state transitions
      for (const key in target) {
        cfg[key] = lerp(cfg[key], target[key], 0.03);
      }

      // Fade previous frame (trail effect) instead of clearing
      ctx.fillStyle = `rgba(10, 10, 15, ${0.15 + cfg.decoherence * 0.15})`;
      ctx.fillRect(0, 0, width, height);

      const particles = particlesRef.current;
      if (!particles) {
        frameRef.current = requestAnimationFrame(animate);
        return;
      }

      // --- Probability cloud (multi-layered gaussian) ---
      for (let layer = 0; layer < 3; layer++) {
        const r = (60 + layer * 40) * cfg.contraction;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        const baseAlpha = cfg.glow * (0.08 - layer * 0.02);
        const hue = layer === 0 ? "74, 168, 255" : layer === 1 ? "120, 140, 255" : "180, 120, 255";
        grad.addColorStop(0, `rgba(${hue}, ${baseAlpha})`);
        grad.addColorStop(0.6, `rgba(${hue}, ${baseAlpha * 0.4})`);
        grad.addColorStop(1, `rgba(${hue}, 0)`);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // --- Vacuum fluctuations: temporary virtual quark-antiquark pairs ---
      const vp = virtualPairsRef.current;
      if (cfg.fluctuation > 0.2 && Math.random() < cfg.fluctuation * 0.03) {
        const colorIdx = Math.floor(Math.random() * 3);
        const angle = Math.random() * Math.PI * 2;
        const dist = 20 + Math.random() * 80;
        const px = cx + Math.cos(angle) * dist;
        const py = cy + Math.sin(angle) * dist;
        vp.push({
          x: px, y: py,
          color: QUARK_COLORS[colorIdx],
          antiColor: ANTIQUARK_COLORS[colorIdx],
          life: 40 + Math.random() * 30,
          maxLife: 40 + Math.random() * 30,
          separation: 0,
          angle: Math.random() * Math.PI * 2,
        });
      }

      for (let i = vp.length - 1; i >= 0; i--) {
        const pair = vp[i];
        pair.life--;
        if (pair.life <= 0) { vp.splice(i, 1); continue; }

        const progress = 1 - pair.life / pair.maxLife;
        // Pairs appear, separate briefly, then annihilate
        pair.separation = Math.sin(progress * Math.PI) * 10;
        const alpha = Math.sin(progress * Math.PI) * 0.4;

        const dx = Math.cos(pair.angle) * pair.separation;
        const dy = Math.sin(pair.angle) * pair.separation;

        // Quark
        ctx.beginPath();
        ctx.arc(pair.x + dx, pair.y + dy, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${pair.color.join(",")}, ${alpha})`;
        ctx.fill();

        // Antiquark
        ctx.beginPath();
        ctx.arc(pair.x - dx, pair.y - dy, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${pair.antiColor.join(",")}, ${alpha})`;
        ctx.fill();

        // Annihilation flash at end
        if (pair.life < 5) {
          ctx.beginPath();
          ctx.arc(pair.x, pair.y, 4 * (1 - pair.life / 5), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${0.15 * (pair.life / 5)})`;
          ctx.fill();
        }
      }

      // --- Update and draw particles ---
      const triplets = {};

      for (const p of particles) {
        p.phase += p.phaseSpeed * cfg.speed;

        if (p.type === "quark") {
          // Color confinement: quarks can't escape their triplet
          // Apply spring force toward triplet center
          const contractionForce = cfg.contraction < 1 ? 0.015 : -0.003;
          p.baseX += (cx - p.baseX) * contractionForce;
          p.baseY += (cy - p.baseY) * contractionForce;

          // Drift
          p.baseX += Math.sin(t * 0.003 + p.phase * 2) * 0.1;
          p.baseY += Math.cos(t * 0.004 + p.phase * 2) * 0.1;

          // Confined orbit within triplet
          p.x = p.baseX + Math.cos(p.phase) * p.confinement;
          p.y = p.baseY + Math.sin(p.phase) * p.confinement;

          // Color charge oscillation (gluon exchange between quarks)
          p.colorPhase += p.colorSpeed * cfg.speed;
          const colorShift = (Math.sin(p.colorPhase) + 1) / 2;

          if (!triplets[p.tripletId]) triplets[p.tripletId] = [];
          triplets[p.tripletId].push(p);

          // Draw quark with color oscillation
          const r = p.color[0] + (QUARK_COLORS[(Math.floor(p.colorPhase / Math.PI) + 1) % 3][0] - p.color[0]) * colorShift * 0.3;
          const g = p.color[1] + (QUARK_COLORS[(Math.floor(p.colorPhase / Math.PI) + 1) % 3][1] - p.color[1]) * colorShift * 0.3;
          const b = p.color[2] + (QUARK_COLORS[(Math.floor(p.colorPhase / Math.PI) + 1) % 3][2] - p.color[2]) * colorShift * 0.3;

          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${r|0}, ${g|0}, ${b|0}, ${p.opacity * cfg.colorIntensity})`;
          ctx.fill();

        } else {
          // Electrons and stardust

          // Heisenberg uncertainty: position jitter inversely proportional to certainty
          const jitterScale = cfg.uncertainty * p.posUncertainty;
          const jx = gaussRandom(0, jitterScale);
          const jy = gaussRandom(0, jitterScale);

          // Orbital motion
          const targetR = p.radius * cfg.contraction;
          p.radius = lerp(p.radius, targetR, 0.01);
          p.angle = p.phase;

          p.x = cx + Math.cos(p.angle) * p.radius + jx;
          p.y = cy + Math.sin(p.angle) * p.radius + jy;

          // Quantum tunneling: particle randomly jumps to a different shell
          if (Math.random() < p.tunnelProb * cfg.tunneling) {
            const newShell = 1 + Math.floor(Math.random() * 4);
            p.radius = orbitalRadius(newShell) * 2.5 * cfg.contraction;
            p.shell = newShell;
          }

          // Draw particle
          const alpha = p.opacity * cfg.colorIntensity;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, ${alpha})`;
          ctx.fill();

          // Superposition ghost: particle exists in another position simultaneously
          if (cfg.superposition > 0.15 && p.type === "electron") {
            p.ghostPhase += p.phaseSpeed * cfg.speed * 0.7;
            const gr = p.ghostRadius * cfg.contraction;
            const gx = cx + Math.cos(p.ghostPhase) * gr + gaussRandom(0, jitterScale * 0.5);
            const gy = cy + Math.sin(p.ghostPhase) * gr + gaussRandom(0, jitterScale * 0.5);
            const ghostAlpha = alpha * cfg.superposition * 0.3;

            ctx.beginPath();
            ctx.arc(gx, gy, p.size * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, ${ghostAlpha})`;
            ctx.fill();

            // Entanglement line between real and ghost (faint)
            if (cfg.superposition > 0.5) {
              ctx.beginPath();
              ctx.moveTo(p.x, p.y);
              ctx.lineTo(gx, gy);
              ctx.strokeStyle = `rgba(${p.color[0]}, ${p.color[1]}, ${p.color[2]}, ${ghostAlpha * 0.3})`;
              ctx.lineWidth = 0.3;
              ctx.stroke();
            }
          }
        }
      }

      // Gluon field lines between confined quarks (spring-like, not straight)
      for (const id in triplets) {
        const tri = triplets[id];
        if (tri.length < 2) continue;

        for (let i = 0; i < tri.length; i++) {
          const a = tri[i];
          const b = tri[(i + 1) % tri.length];

          // Wavy gluon line (gluons carry color charge, shown as oscillating connection)
          ctx.beginPath();
          const steps = 8;
          for (let s = 0; s <= steps; s++) {
            const frac = s / steps;
            const mx = lerp(a.x, b.x, frac);
            const my = lerp(a.y, b.y, frac);
            const perpX = -(b.y - a.y) / Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + 0.01);
            const perpY = (b.x - a.x) / Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + 0.01);
            const wave = Math.sin(frac * Math.PI * 3 + t * 0.05) * 3;
            const px = mx + perpX * wave;
            const py = my + perpY * wave;
            if (s === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.strokeStyle = `rgba(200, 180, 255, ${0.08 * cfg.colorIntensity})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
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
