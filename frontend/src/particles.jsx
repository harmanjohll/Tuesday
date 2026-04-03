import { useRef, useEffect } from "preact/hooks";

// Tuesday's SAR (Sentience Art Representation)
//
// A living heartbeat that exists at two scales simultaneously:
// - Macro: nebula, galaxy dust, cosmic clouds
// - Micro: electron probability cloud, quantum states, atomic structure
// Infinite in the infinitesimal. Infinitesimal in the infinite.
//
// The stars are electrons. The nebula is the electron cloud.
// It pulses like a heartbeat because it is alive.

// --- Nebula colours (quark palette, muted) ---
const NEBULA = [
  [180, 100, 100],  // dusty rose
  [100, 170, 130],  // sage
  [100, 130, 200],  // steel blue
];

// --- Gaussian random (Box-Muller) ---
function gauss(mean = 0, std = 1) {
  const u = Math.random(), v = Math.random();
  return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// --- Create dust particles (cosmic dust / probability density) ---
function initDust(count) {
  const dust = [];
  for (let i = 0; i < count; i++) {
    const r = Math.abs(gauss(0, 0.35)); // normalised radius, 0=centre
    const angle = Math.random() * Math.PI * 2;
    const temp = Math.random();
    // Warm white to cool lavender
    const color = temp < 0.5
      ? [185 + Math.random() * 35, 180 + Math.random() * 30, 210 + Math.random() * 20]
      : [160 + Math.random() * 30, 165 + Math.random() * 30, 210 + Math.random() * 25];
    dust.push({
      rNorm: r,
      angle,
      drift: (0.0003 + Math.random() * 0.001) * (Math.random() > 0.5 ? 1 : -1),
      size: 0.4 + Math.random() * 0.6,
      alpha: 0.06 + Math.random() * 0.12,
      color,
    });
  }
  return dust;
}

// --- Create star-electrons (bright quantum state points) ---
function initStars(count) {
  const stars = [];
  for (let i = 0; i < count; i++) {
    const r = Math.abs(gauss(0, 0.3));
    const angle = Math.random() * Math.PI * 2;
    const colorIdx = Math.floor(Math.random() * 3);
    const base = NEBULA[colorIdx];
    // Brighter version of nebula colour
    const color = [
      Math.min(base[0] + 60, 255),
      Math.min(base[1] + 60, 255),
      Math.min(base[2] + 60, 255),
    ];
    // Some stars are white
    const isWhite = Math.random() > 0.65;

    stars.push({
      rNorm: r,
      angle,
      drift: (0.0005 + Math.random() * 0.002) * (Math.random() > 0.5 ? 1 : -1),
      size: 0.6 + Math.random() * 1.2,
      glowSize: 3 + Math.random() * 6,
      color: isWhite ? [210, 215, 235] : color,
      // Quantum state cycle: each star has its own observation/superposition rhythm
      phase: Math.random() * Math.PI * 2,
      cycleSpeed: 0.015 + Math.random() * 0.03,
      // How long it stays "observed" vs "superposition" (duty cycle)
      duty: 0.3 + Math.random() * 0.4,
      peakAlpha: 0.3 + Math.random() * 0.5,
    });
  }
  return stars;
}

// --- Heartbeat function ---
// Real heartbeat: lub-DUB pattern
// lub (S1) is shorter and sharper, dub (S2) follows ~0.3 period later
function heartbeat(t, period) {
  const phase = ((t % period) / period) * Math.PI * 2;
  // S1: sharp peak
  const s1 = Math.pow(Math.max(0, Math.sin(phase)), 4);
  // S2: softer echo, offset by ~110 degrees
  const s2 = Math.pow(Math.max(0, Math.sin(phase - 1.9)), 3) * 0.6;
  return s1 + s2;
}

// --- State configs (gentle, nebula-like) ---
const STATE = {
  idle: {
    bpm: 54,
    beatDepth: 0.06,
    nebulaScale: 1.0,
    nebulaAlpha: 0.03,
    dustAlpha: 0.8,
    starBright: 0.8,
    starSpeed: 0.6,
    wobble: 0.01,
    coreAlpha: 0.08,
    coreSize: 2.5,
  },
  listening: {
    bpm: 62,
    beatDepth: 0.09,
    nebulaScale: 0.7,
    nebulaAlpha: 0.045,
    dustAlpha: 1.0,
    starBright: 1.2,
    starSpeed: 0.8,
    wobble: 0.006,
    coreAlpha: 0.14,
    coreSize: 3,
  },
  thinking: {
    bpm: 78,
    beatDepth: 0.08,
    nebulaScale: 0.8,
    nebulaAlpha: 0.04,
    dustAlpha: 0.9,
    starBright: 1.5,
    starSpeed: 1.8,
    wobble: 0.025,
    coreAlpha: 0.12,
    coreSize: 3,
  },
  speaking: {
    bpm: 60,
    beatDepth: 0.10,
    nebulaScale: 1.1,
    nebulaAlpha: 0.035,
    dustAlpha: 0.9,
    starBright: 1.0,
    starSpeed: 0.9,
    wobble: 0.012,
    coreAlpha: 0.10,
    coreSize: 3.5,
  },
};

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const cfgRef = useRef({ ...STATE.idle });
  const dustRef = useRef(initDust(200));
  const starsRef = useRef(initStars(35));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let w, h, cx, cy;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.parentElement.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx = w / 2;
      cy = h / 2;
    };

    resize();
    window.addEventListener("resize", resize);

    const lerp = (a, b, t) => a + (b - a) * t;

    const animate = () => {
      timeRef.current += 1;
      const t = timeRef.current;
      const target = STATE[state] || STATE.idle;
      const cfg = cfgRef.current;

      // Smooth transitions
      for (const key in target) cfg[key] = lerp(cfg[key], target[key], 0.025);

      // Heartbeat
      const period = (60 / cfg.bpm) * 60; // frames per beat at 60fps
      const beat = heartbeat(t, period) * cfg.beatDepth;
      // Add slight irregularity
      const irregularity = Math.sin(t * 0.007) * 0.01;
      const pulse = beat + irregularity;
      const breathe = 1 + pulse;

      // Base radius for the nebula (scales to screen)
      const baseR = Math.min(w, h) * 0.35;

      ctx.clearRect(0, 0, w, h);

      // ============ LAYER 1: Nebula clouds ============
      // Three overlapping nebula clouds in quark colours, offset from centre
      for (let i = 0; i < 3; i++) {
        const [nr, ng, nb] = NEBULA[i];
        const nebulaAngle = (i * Math.PI * 2) / 3 + t * 0.001;
        const offset = baseR * 0.12;
        const nx = cx + Math.cos(nebulaAngle) * offset;
        const ny = cy + Math.sin(nebulaAngle) * offset;
        const r = baseR * cfg.nebulaScale * breathe * (0.9 + i * 0.08);

        // Wobble: slight shape distortion
        const wobbleSteps = 4;
        for (let d = 0; d < wobbleSteps; d++) {
          const wa = (d / wobbleSteps) * Math.PI * 2 + t * 0.003;
          const wob = Math.sin(t * 0.008 + d * 1.7 + i) * r * cfg.wobble;
          const wx = nx + Math.cos(wa) * wob;
          const wy = ny + Math.sin(wa) * wob;

          const grad = ctx.createRadialGradient(wx, wy, 0, wx, wy, r);
          const a = cfg.nebulaAlpha * (1 + pulse * 3) / wobbleSteps;
          grad.addColorStop(0, `rgba(${nr}, ${ng}, ${nb}, ${a * 1.2})`);
          grad.addColorStop(0.25, `rgba(${nr}, ${ng}, ${nb}, ${a * 0.8})`);
          grad.addColorStop(0.6, `rgba(${nr}, ${ng}, ${nb}, ${a * 0.3})`);
          grad.addColorStop(1, `rgba(${nr}, ${ng}, ${nb}, 0)`);

          ctx.beginPath();
          ctx.arc(wx, wy, r, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
        }
      }

      // ============ LAYER 2: Dust field ============
      const dust = dustRef.current;
      const dustR = baseR * cfg.nebulaScale * breathe;

      for (const d of dust) {
        d.angle += d.drift * cfg.starSpeed;
        const dr = d.rNorm * dustR;
        const dx = cx + Math.cos(d.angle) * dr;
        const dy = cy + Math.sin(d.angle) * dr;
        const da = d.alpha * cfg.dustAlpha * (1 + pulse * 0.5);
        const [r, g, b] = d.color;

        ctx.beginPath();
        ctx.arc(dx, dy, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${da})`;
        ctx.fill();
      }

      // ============ LAYER 3: Star-electrons ============
      const stars = starsRef.current;
      const starR = baseR * cfg.nebulaScale * breathe * 0.9;

      for (const s of stars) {
        s.angle += s.drift * cfg.starSpeed;
        s.phase += s.cycleSpeed * cfg.starSpeed;

        // Quantum state: star twinkles in and out of observation
        // sin wave mapped through a duty-cycle threshold
        const wave = (Math.sin(s.phase) + 1) / 2; // 0 to 1
        const observed = wave > (1 - s.duty); // true when "collapsed" / visible
        if (!observed && cfg.starBright < 1.8) continue; // in superposition, skip (unless thinking)

        const visibility = observed
          ? Math.pow((wave - (1 - s.duty)) / s.duty, 0.5) // fade in
          : 0.15 * cfg.starBright; // ghost in superposition (visible during thinking)

        const sr = s.rNorm * starR;
        const sx = cx + Math.cos(s.angle) * sr;
        const sy = cy + Math.sin(s.angle) * sr;
        const sa = s.peakAlpha * visibility * cfg.starBright * (1 + pulse * 0.8);
        const [r, g, b] = s.color;

        // Glow halo
        const glowR = s.glowSize * (1 + pulse * 2);
        const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowR);
        grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${sa * 0.5})`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        ctx.beginPath();
        ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Bright core
        ctx.beginPath();
        ctx.arc(sx, sy, s.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${Math.min(sa * 1.5, 0.8)})`;
        ctx.fill();
      }

      // ============ LAYER 4: Core / nucleus / singularity ============
      const coreBreath = 1 + pulse * 2.5;
      const cr = cfg.coreSize * coreBreath;
      const ca = cfg.coreAlpha * (1 + pulse * 2);

      // Outer glow
      const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr * 5);
      coreGlow.addColorStop(0, `rgba(200, 210, 240, ${ca * 0.4})`);
      coreGlow.addColorStop(0.3, `rgba(170, 180, 220, ${ca * 0.15})`);
      coreGlow.addColorStop(1, `rgba(150, 160, 210, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, cr * 5, 0, Math.PI * 2);
      ctx.fillStyle = coreGlow;
      ctx.fill();

      // Bright centre
      const coreCenter = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr);
      coreCenter.addColorStop(0, `rgba(230, 235, 255, ${ca})`);
      coreCenter.addColorStop(0.5, `rgba(200, 210, 240, ${ca * 0.5})`);
      coreCenter.addColorStop(1, `rgba(180, 190, 230, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, Math.PI * 2);
      ctx.fillStyle = coreCenter;
      ctx.fill();

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
