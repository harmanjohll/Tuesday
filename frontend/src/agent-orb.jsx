import { useRef, useEffect } from "preact/hooks";

/**
 * AgentOrb — A small, colored particle system representing a single agent.
 *
 * Simplified version of Tuesday's QuantumField. Each agent gets a unique
 * color identity. The orb pulses based on the agent's status:
 *   - idle: slow, steady breathing
 *   - working: faster pulse, more particles visible
 *   - done: bright glow, steady
 *   - error: flicker
 */

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

const STATUS_CONFIG = {
  idle: { bpm: 50, beatDepth: 0.04, brightness: 0.6, speed: 0.3 },
  working: { bpm: 80, beatDepth: 0.12, brightness: 1.0, speed: 1.2 },
  done: { bpm: 45, beatDepth: 0.03, brightness: 0.9, speed: 0.2 },
  error: { bpm: 100, beatDepth: 0.15, brightness: 0.4, speed: 0.5 },
};

function heartbeat(t, period) {
  const phase = ((t % period) / period) * Math.PI * 2;
  return Math.pow(Math.max(0, Math.sin(phase)), 4);
}

export function AgentOrb({ color = "#FF6B6B", status = "idle", size = 80 }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(Math.random() * 1000); // Random offset so orbs don't sync
  const dustRef = useRef(null);
  const starsRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = size + "px";
    canvas.style.height = size + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cx = size / 2;
    const cy = size / 2;
    const baseR = size * 0.38;
    const rgb = hexToRgb(color);

    // Initialize particles once
    if (!dustRef.current) {
      const dust = [];
      for (let i = 0; i < 40; i++) {
        const r = Math.random() * 0.9;
        const angle = Math.random() * Math.PI * 2;
        dust.push({
          rNorm: r,
          angle,
          drift: (0.001 + Math.random() * 0.003) * (Math.random() > 0.5 ? 1 : -1),
          size: 0.3 + Math.random() * 0.5,
          alpha: 0.08 + Math.random() * 0.15,
        });
      }
      dustRef.current = dust;
    }

    if (!starsRef.current) {
      const stars = [];
      for (let i = 0; i < 12; i++) {
        stars.push({
          rNorm: Math.random() * 0.8,
          angle: Math.random() * Math.PI * 2,
          drift: (0.002 + Math.random() * 0.005) * (Math.random() > 0.5 ? 1 : -1),
          size: 0.5 + Math.random() * 0.8,
          glowSize: 2 + Math.random() * 3,
          phase: Math.random() * Math.PI * 2,
          cycleSpeed: 0.02 + Math.random() * 0.03,
          duty: 0.4 + Math.random() * 0.3,
          peakAlpha: 0.4 + Math.random() * 0.4,
        });
      }
      starsRef.current = stars;
    }

    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
    let currentCfg = { ...cfg };

    const animate = () => {
      timeRef.current += 1;
      const t = timeRef.current;

      // Lerp config
      for (const key in cfg) {
        currentCfg[key] = currentCfg[key] + (cfg[key] - currentCfg[key]) * 0.03;
      }

      const period = (60 / currentCfg.bpm) * 60;
      const beat = heartbeat(t, period) * currentCfg.beatDepth;
      const breathe = 1 + beat;

      ctx.clearRect(0, 0, size, size);

      // Core glow
      const coreR = baseR * 0.5 * breathe;
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
      const coreAlpha = 0.25 * currentCfg.brightness * (1 + beat * 3);
      coreGrad.addColorStop(0, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${coreAlpha})`);
      coreGrad.addColorStop(0.4, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${coreAlpha * 0.4})`);
      coreGrad.addColorStop(1, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
      ctx.fill();

      // Dust
      const dust = dustRef.current;
      for (const d of dust) {
        d.angle += d.drift * currentCfg.speed;
        const dr = d.rNorm * baseR * breathe;
        const dx = cx + Math.cos(d.angle) * dr;
        const dy = cy + Math.sin(d.angle) * dr;
        const da = d.alpha * currentCfg.brightness * (1 + beat * 0.5);

        ctx.beginPath();
        ctx.arc(dx, dy, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${da})`;
        ctx.fill();
      }

      // Stars
      const stars = starsRef.current;
      for (const s of stars) {
        s.angle += s.drift * currentCfg.speed;
        s.phase += s.cycleSpeed * currentCfg.speed;

        const wave = (Math.sin(s.phase) + 1) / 2;
        if (wave < 1 - s.duty) continue;

        const visibility = Math.pow((wave - (1 - s.duty)) / s.duty, 0.5);
        const sr = s.rNorm * baseR * breathe;
        const sx = cx + Math.cos(s.angle) * sr;
        const sy = cy + Math.sin(s.angle) * sr;
        const sa = s.peakAlpha * visibility * currentCfg.brightness * (1 + beat * 0.8);

        // Glow
        const glowR = s.glowSize * (1 + beat * 2);
        const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowR);
        grad.addColorStop(0, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${sa * 0.5})`);
        grad.addColorStop(1, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0)`);
        ctx.beginPath();
        ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(sx, sy, s.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${Math.min(rgb[0] + 60, 255)}, ${Math.min(rgb[1] + 60, 255)}, ${Math.min(rgb[2] + 60, 255)}, ${Math.min(sa * 1.5, 0.9)})`;
        ctx.fill();
      }

      // Pulse ring (working only)
      if (status === "working") {
        const ringPhase = (t % 90) / 90;
        const ringR = baseR * 0.3 + baseR * 0.7 * ringPhase;
        const ringAlpha = (1 - ringPhase) * 0.12;
        ctx.beginPath();
        ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${ringAlpha})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [color, status, size]);

  return (
    <canvas
      ref={canvasRef}
      class="agent-orb-canvas"
      aria-hidden="true"
      style={{ width: size + "px", height: size + "px" }}
    />
  );
}
