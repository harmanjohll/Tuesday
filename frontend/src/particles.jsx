import { useRef, useEffect } from "preact/hooks";

// Tuesday's visual presence: a living, pulsing orb
// Not scattered particles — a cohesive luminous form that breathes
// Concentric layered glows that expand/contract with state changes

// Muted palette
const COLORS = {
  core:   [160, 170, 220],   // soft blue-lavender
  inner:  [140, 150, 210],   // lavender
  mid:    [120, 140, 200],   // steel blue
  outer:  [100, 130, 190],   // deep steel
  accent1: [180, 100, 100],  // dusty rose
  accent2: [100, 170, 130],  // sage
  accent3: [100, 130, 200],  // steel blue
};

// Pulse rhythm per state
const PULSE_CONFIG = {
  idle:      { period: 240, depth: 0.12, secondary: 0.06, speed: 1 },
  listening: { period: 120, depth: 0.25, secondary: 0.12, speed: 1.5 },
  thinking:  { period: 30,  depth: 0.18, secondary: 0.15, speed: 3 },
  speaking:  { period: 90,  depth: 0.20, secondary: 0.10, speed: 1.8 },
};

// Orb shape per state
const STATE_CONFIG = {
  idle: {
    coreRadius: 30,
    innerRadius: 60,
    midRadius: 100,
    outerRadius: 160,
    coreAlpha: 0.12,
    innerAlpha: 0.07,
    midAlpha: 0.04,
    outerAlpha: 0.02,
    distortion: 0.02,
    accentCount: 3,
    accentAlpha: 0.03,
    colorIntensity: 0.5,
  },
  listening: {
    coreRadius: 22,
    innerRadius: 40,
    midRadius: 65,
    outerRadius: 100,
    coreAlpha: 0.25,
    innerAlpha: 0.15,
    midAlpha: 0.08,
    outerAlpha: 0.04,
    distortion: 0.01,
    accentCount: 2,
    accentAlpha: 0.06,
    colorIntensity: 0.85,
  },
  thinking: {
    coreRadius: 25,
    innerRadius: 50,
    midRadius: 85,
    outerRadius: 130,
    coreAlpha: 0.20,
    innerAlpha: 0.12,
    midAlpha: 0.07,
    outerAlpha: 0.035,
    distortion: 0.06,
    accentCount: 5,
    accentAlpha: 0.05,
    colorIntensity: 0.75,
  },
  speaking: {
    coreRadius: 35,
    innerRadius: 70,
    midRadius: 120,
    outerRadius: 190,
    coreAlpha: 0.18,
    innerAlpha: 0.10,
    midAlpha: 0.05,
    outerAlpha: 0.025,
    distortion: 0.03,
    accentCount: 4,
    accentAlpha: 0.04,
    colorIntensity: 0.65,
  },
};

// Pre-generate speckle positions (stable across frames)
function initSpeckles(count) {
  const speckles = [];
  for (let i = 0; i < count; i++) {
    // Gaussian distribution — denser toward center
    const u1 = Math.random(), u2 = Math.random();
    const r = Math.abs(Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2));
    const angle = Math.random() * Math.PI * 2;
    const colorTemp = Math.random();
    let color;
    if (colorTemp < 0.15) color = COLORS.accent1;
    else if (colorTemp < 0.30) color = COLORS.accent2;
    else if (colorTemp < 0.45) color = COLORS.accent3;
    else color = [180 + Math.random() * 40, 185 + Math.random() * 35, 220 + Math.random() * 20];

    speckles.push({
      rNorm: r,           // normalized radius (0 = center, ~3 = far edge)
      angle,
      phase: Math.random() * Math.PI * 2,
      twinkleSpeed: 0.02 + Math.random() * 0.04,
      size: 0.4 + Math.random() * 1.0,
      baseAlpha: 0.15 + Math.random() * 0.35,
      color,
      drift: 0.0005 + Math.random() * 0.002,
    });
  }
  return speckles;
}

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const cfgRef = useRef({ ...STATE_CONFIG.idle });
  const pulseRef = useRef({ ...PULSE_CONFIG.idle });
  const specklesRef = useRef(initSpeckles(150));

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

      // Smooth state transitions
      for (const key in target) cfg[key] = lerp(cfg[key], target[key], 0.03);
      for (const key in targetPulse) pulse[key] = lerp(pulse[key], targetPulse[key], 0.03);

      // Primary heartbeat
      const beat = Math.sin((t / pulse.period) * Math.PI * 2);
      const heartbeat = beat * pulse.depth;

      // Secondary pulse (slightly offset, creates organic rhythm)
      const beat2 = Math.sin((t / (pulse.period * 1.618)) * Math.PI * 2); // golden ratio offset
      const secondary = beat2 * pulse.secondary;

      // Breathing scale
      const breathe = 1 + heartbeat + secondary * 0.5;

      ctx.clearRect(0, 0, width, height);

      // --- Draw the orb as concentric pulsing layers ---

      const layers = [
        { radius: cfg.outerRadius, color: COLORS.outer, alpha: cfg.outerAlpha, phaseOff: 0 },
        { radius: cfg.midRadius, color: COLORS.mid, alpha: cfg.midAlpha, phaseOff: 0.5 },
        { radius: cfg.innerRadius, color: COLORS.inner, alpha: cfg.innerAlpha, phaseOff: 1.0 },
        { radius: cfg.coreRadius, color: COLORS.core, alpha: cfg.coreAlpha, phaseOff: 1.5 },
      ];

      for (const layer of layers) {
        // Each layer pulses slightly out of phase for organic feel
        const layerBreath = 1 + heartbeat * (1 + layer.phaseOff * 0.2)
          + Math.sin((t / pulse.period) * Math.PI * 2 + layer.phaseOff) * pulse.secondary * 0.3;

        const r = layer.radius * layerBreath;
        const [cr, cg, cb] = layer.color;
        const a = layer.alpha * (1 + heartbeat * 0.5);

        // Soft distortion: draw multiple offset circles for organic wobble
        const distortionSteps = 5;
        for (let d = 0; d < distortionSteps; d++) {
          const angle = (d / distortionSteps) * Math.PI * 2 + t * 0.002;
          const wobble = Math.sin(t * 0.01 + d * 1.3) * r * cfg.distortion;
          const dx = Math.cos(angle) * wobble;
          const dy = Math.sin(angle) * wobble;

          const grad = ctx.createRadialGradient(
            cx + dx, cy + dy, 0,
            cx + dx, cy + dy, r
          );
          const stepAlpha = a / distortionSteps;
          grad.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${stepAlpha * 1.5})`);
          grad.addColorStop(0.3, `rgba(${cr}, ${cg}, ${cb}, ${stepAlpha})`);
          grad.addColorStop(0.7, `rgba(${cr}, ${cg}, ${cb}, ${stepAlpha * 0.4})`);
          grad.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);

          ctx.beginPath();
          ctx.arc(cx + dx, cy + dy, r, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
        }
      }

      // --- Colour accents: subtle coloured spots that drift within the orb ---
      const accents = [COLORS.accent1, COLORS.accent2, COLORS.accent3];
      for (let i = 0; i < Math.round(cfg.accentCount); i++) {
        const color = accents[i % 3];
        const angle = (i * 2.39996) + t * 0.003 * (i % 2 === 0 ? 1 : -1); // golden angle
        const dist = cfg.innerRadius * 0.5 * breathe * (0.3 + Math.sin(t * 0.005 + i * 2) * 0.3);
        const ax = cx + Math.cos(angle) * dist;
        const ay = cy + Math.sin(angle) * dist;
        const ar = 15 + Math.sin(t * 0.008 + i) * 8;
        const aa = cfg.accentAlpha * (1 + heartbeat * 0.3);
        const [r, g, b] = color;

        const grad = ctx.createRadialGradient(ax, ay, 0, ax, ay, ar * breathe);
        grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${aa})`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        ctx.beginPath();
        ctx.arc(ax, ay, ar * breathe, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // --- Speckles: fine luminous points within the orb ---
      const speckles = specklesRef.current;
      for (const s of speckles) {
        s.phase += s.twinkleSpeed * pulse.speed;
        s.angle += s.drift * pulse.speed;

        // Place speckle within the orb boundary (scaled by outer radius and breath)
        const maxR = cfg.outerRadius * 0.85 * breathe;
        const sr = s.rNorm * (maxR / 3); // /3 because gaussian rNorm peaks around 0-3
        const sx = cx + Math.cos(s.angle) * sr;
        const sy = cy + Math.sin(s.angle) * sr;

        // Twinkle: sinusoidal alpha modulation + global heartbeat
        const twinkle = (Math.sin(s.phase) + 1) / 2; // 0 to 1
        const sa = s.baseAlpha * twinkle * cfg.colorIntensity * (1 + heartbeat * 0.4);
        const [sr2, sg, sb] = s.color;

        // Only draw if visible
        if (sa > 0.02) {
          // Tiny glow
          const glowR = s.size * 3;
          const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowR);
          grad.addColorStop(0, `rgba(${sr2}, ${sg}, ${sb}, ${sa * 0.6})`);
          grad.addColorStop(1, `rgba(${sr2}, ${sg}, ${sb}, 0)`);
          ctx.beginPath();
          ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();

          // Bright core
          ctx.beginPath();
          ctx.arc(sx, sy, s.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${sr2}, ${sg}, ${sb}, ${Math.min(sa * 1.2, 0.7)})`;
          ctx.fill();
        }
      }

      // --- Core bright point: the "eye" of the orb ---
      const coreBreath = 1 + heartbeat * 1.5 + secondary;
      const coreR = 4 * coreBreath;
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
      const coreA = 0.15 + heartbeat * 0.1;
      coreGrad.addColorStop(0, `rgba(220, 225, 255, ${coreA})`);
      coreGrad.addColorStop(0.5, `rgba(180, 190, 240, ${coreA * 0.5})`);
      coreGrad.addColorStop(1, `rgba(160, 170, 220, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
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
