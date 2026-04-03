import { useRef, useEffect } from "preact/hooks";

// Tuesday's SAR (Sentience Art Representation)
//
// A living heartbeat that exists at two scales simultaneously:
// - Macro: nebula, galaxy dust, cosmic clouds
// - Micro: electron probability cloud, quantum states, atomic structure
// Infinite in the infinitesimal. Infinitesimal in the infinite.
//
// The stars are electrons. The nebula is the electron cloud.
// Inside the atom's core: the cosmos itself. A nebula pulsing.
// Infinity is within the nothing, and vice versa.

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
    const r = Math.abs(gauss(0, 0.35));
    const angle = Math.random() * Math.PI * 2;
    const temp = Math.random();
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
    const color = [
      Math.min(base[0] + 60, 255),
      Math.min(base[1] + 60, 255),
      Math.min(base[2] + 60, 255),
    ];
    const isWhite = Math.random() > 0.65;

    stars.push({
      rNorm: r,
      angle,
      drift: (0.0005 + Math.random() * 0.002) * (Math.random() > 0.5 ? 1 : -1),
      size: 0.6 + Math.random() * 1.2,
      glowSize: 3 + Math.random() * 6,
      color: isWhite ? [210, 215, 235] : color,
      phase: Math.random() * Math.PI * 2,
      cycleSpeed: 0.015 + Math.random() * 0.03,
      duty: 0.3 + Math.random() * 0.4,
      peakAlpha: 0.3 + Math.random() * 0.5,
    });
  }
  return stars;
}

// --- Generate procedural nebula texture (Eagle Nebula palette) ---
// Used when /nebula.jpg is not available.
// Rose-pink gas clouds, bright stellar core, deep space black, scattered stars.
function generateNebulaTexture(size) {
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  const ctx = c.getContext("2d");

  // Deep space background
  ctx.fillStyle = "#050510";
  ctx.fillRect(0, 0, size, size);

  const cx = size / 2, cy = size / 2;

  // Gas clouds — layered radial gradients, asymmetric
  const clouds = [
    { x: cx * 0.7, y: cy * 0.6, r: size * 0.5, color: [180, 60, 80], a: 0.15 },    // deep rose, left
    { x: cx * 1.1, y: cy * 0.9, r: size * 0.45, color: [200, 100, 120], a: 0.12 },  // pink, center-right
    { x: cx * 0.9, y: cy * 1.2, r: size * 0.4, color: [170, 80, 110], a: 0.1 },     // magenta, bottom
    { x: cx, y: cy, r: size * 0.3, color: [210, 190, 200], a: 0.14 },                // bright core wash
    { x: cx * 1.05, y: cy * 0.85, r: size * 0.22, color: [220, 220, 240], a: 0.18 }, // white-blue stellar core
    { x: cx * 0.6, y: cy * 0.4, r: size * 0.3, color: [120, 40, 50], a: 0.08 },     // dark red upper-left
    { x: cx * 1.3, y: cy * 1.3, r: size * 0.25, color: [80, 60, 120], a: 0.06 },    // purple corner
  ];

  for (const cl of clouds) {
    const g = ctx.createRadialGradient(cl.x, cl.y, 0, cl.x, cl.y, cl.r);
    const [r, gn, b] = cl.color;
    g.addColorStop(0, `rgba(${r}, ${gn}, ${b}, ${cl.a})`);
    g.addColorStop(0.3, `rgba(${r}, ${gn}, ${b}, ${cl.a * 0.7})`);
    g.addColorStop(0.6, `rgba(${r}, ${gn}, ${b}, ${cl.a * 0.3})`);
    g.addColorStop(1, `rgba(${r}, ${gn}, ${b}, 0)`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }

  // Dark dust lanes (subtract light in streaks)
  ctx.globalCompositeOperation = "multiply";
  for (let i = 0; i < 3; i++) {
    const dx = cx * (0.8 + Math.random() * 0.4);
    const dy = cy * (0.7 + Math.random() * 0.6);
    const dr = size * (0.08 + Math.random() * 0.12);
    const dg = ctx.createRadialGradient(dx, dy, 0, dx, dy, dr);
    dg.addColorStop(0, "rgba(10, 8, 15, 1)");
    dg.addColorStop(0.5, "rgba(30, 20, 30, 1)");
    dg.addColorStop(1, "rgba(255, 255, 255, 1)");
    ctx.fillStyle = dg;
    ctx.fillRect(0, 0, size, size);
  }
  ctx.globalCompositeOperation = "source-over";

  // Scattered stars
  for (let i = 0; i < 300; i++) {
    const sx = Math.random() * size;
    const sy = Math.random() * size;
    const ss = 0.3 + Math.random() * 1.5;
    const bright = Math.random();

    // Star color: mostly white-blue, some warm
    let sr, sg, sb;
    if (bright > 0.92) {
      // Bright orange/red star
      sr = 255; sg = 150 + Math.random() * 80; sb = 100 + Math.random() * 50;
    } else if (bright > 0.7) {
      // Blue-white
      sr = 180 + Math.random() * 75; sg = 190 + Math.random() * 65; sb = 255;
    } else {
      // White
      sr = 200 + Math.random() * 55; sg = 200 + Math.random() * 55; sb = 210 + Math.random() * 45;
    }

    const sa = 0.3 + Math.random() * 0.7;

    // Glow
    if (ss > 0.8) {
      const gg = ctx.createRadialGradient(sx, sy, 0, sx, sy, ss * 4);
      gg.addColorStop(0, `rgba(${sr}, ${sg}, ${sb}, ${sa * 0.3})`);
      gg.addColorStop(1, `rgba(${sr}, ${sg}, ${sb}, 0)`);
      ctx.fillStyle = gg;
      ctx.fillRect(sx - ss * 4, sy - ss * 4, ss * 8, ss * 8);
    }

    // Core
    ctx.beginPath();
    ctx.arc(sx, sy, ss, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${sa})`;
    ctx.fill();
  }

  return c;
}

// --- Load nebula image or generate procedural fallback ---
function loadNebulaTexture() {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => {
      // Fallback: generate procedural nebula
      console.log("Nebula image not found — generating procedural texture");
      resolve(generateNebulaTexture(1024));
    };
    img.src = "/nebula.jpg";
  });
}

// --- Heartbeat function ---
function heartbeat(t, period) {
  const phase = ((t % period) / period) * Math.PI * 2;
  const s1 = Math.pow(Math.max(0, Math.sin(phase)), 4);
  const s2 = Math.pow(Math.max(0, Math.sin(phase - 1.9)), 3) * 0.6;
  return s1 + s2;
}

// --- State configs ---
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
    // Nebula-in-atom settings
    innerNebulaSize: 0.18,   // fraction of baseR
    innerNebulaAlpha: 0.55,
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
    innerNebulaSize: 0.22,
    innerNebulaAlpha: 0.65,
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
    innerNebulaSize: 0.25,
    innerNebulaAlpha: 0.75,
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
    innerNebulaSize: 0.20,
    innerNebulaAlpha: 0.60,
  },
};

export function QuantumField({ state = "idle" }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const timeRef = useRef(0);
  const cfgRef = useRef({ ...STATE.idle });
  const dustRef = useRef(initDust(200));
  const starsRef = useRef(initStars(35));
  const nebulaTextureRef = useRef(null);

  // Load nebula texture once
  useEffect(() => {
    loadNebulaTexture().then((tex) => {
      nebulaTextureRef.current = tex;
    });
  }, []);

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

      for (const key in target) cfg[key] = lerp(cfg[key], target[key], 0.025);

      // Heartbeat
      const period = (60 / cfg.bpm) * 60;
      const beat = heartbeat(t, period) * cfg.beatDepth;
      const irregularity = Math.sin(t * 0.007) * 0.01;
      const pulse = beat + irregularity;
      const breathe = 1 + pulse;

      const baseR = Math.min(w, h) * 0.35;

      ctx.clearRect(0, 0, w, h);

      // ============ LAYER 1: Nebula clouds ============
      for (let i = 0; i < 3; i++) {
        const [nr, ng, nb] = NEBULA[i];
        const nebulaAngle = (i * Math.PI * 2) / 3 + t * 0.001;
        const offset = baseR * 0.12;
        const nx = cx + Math.cos(nebulaAngle) * offset;
        const ny = cy + Math.sin(nebulaAngle) * offset;
        const r = baseR * cfg.nebulaScale * breathe * (0.9 + i * 0.08);

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

        const wave = (Math.sin(s.phase) + 1) / 2;
        const observed = wave > (1 - s.duty);
        if (!observed && cfg.starBright < 1.8) continue;

        const visibility = observed
          ? Math.pow((wave - (1 - s.duty)) / s.duty, 0.5)
          : 0.15 * cfg.starBright;

        const sr = s.rNorm * starR;
        const sx = cx + Math.cos(s.angle) * sr;
        const sy = cy + Math.sin(s.angle) * sr;
        const sa = s.peakAlpha * visibility * cfg.starBright * (1 + pulse * 0.8);
        const [r, g, b] = s.color;

        const glowR = s.glowSize * (1 + pulse * 2);
        const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowR);
        grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${sa * 0.5})`);
        grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        ctx.beginPath();
        ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(sx, sy, s.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${Math.min(sa * 1.5, 0.8)})`;
        ctx.fill();
      }

      // ============ LAYER 4: Core — the cosmos within ============
      // The subversion: inside the atom, infinity.
      // The nebula image (or procedural texture) lives here,
      // clipped to a pulsing circle, slowly rotating.

      const nebTex = nebulaTextureRef.current;
      const coreBreath = 1 + pulse * 2.5;
      const innerR = baseR * cfg.innerNebulaSize * coreBreath;
      const innerAlpha = cfg.innerNebulaAlpha * (0.8 + pulse * 1.5);

      if (nebTex && innerR > 1) {
        ctx.save();

        // Clip to circular region at centre
        ctx.beginPath();
        ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
        ctx.clip();

        // Soft fade: draw a radial gradient mask after the image
        // First draw the image, rotated slowly
        ctx.globalAlpha = Math.min(innerAlpha, 0.85);
        const rot = t * 0.0003; // very slow rotation
        ctx.translate(cx, cy);
        ctx.rotate(rot);

        // Scale image to fill the clipped circle, slightly larger to allow rotation
        const imgSize = innerR * 2.4;
        ctx.drawImage(nebTex, -imgSize / 2, -imgSize / 2, imgSize, imgSize);

        ctx.rotate(-rot);
        ctx.translate(-cx, -cy);

        // Feathered edge: radial gradient that fades the edges to black/transparent
        const edgeFade = ctx.createRadialGradient(cx, cy, innerR * 0.5, cx, cy, innerR);
        edgeFade.addColorStop(0, "rgba(0, 0, 0, 0)");
        edgeFade.addColorStop(0.7, "rgba(0, 0, 0, 0)");
        edgeFade.addColorStop(1, "rgba(5, 5, 16, 0.9)");
        ctx.globalAlpha = 1;
        ctx.fillStyle = edgeFade;
        ctx.beginPath();
        ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }

      // Outer core glow (surrounds the nebula window)
      const cr = cfg.coreSize * coreBreath;
      const ca = cfg.coreAlpha * (1 + pulse * 2);

      const coreGlow = ctx.createRadialGradient(cx, cy, innerR * 0.8, cx, cy, innerR + cr * 5);
      coreGlow.addColorStop(0, `rgba(200, 180, 210, ${ca * 0.3})`);
      coreGlow.addColorStop(0.3, `rgba(180, 160, 200, ${ca * 0.12})`);
      coreGlow.addColorStop(1, `rgba(150, 140, 190, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, innerR + cr * 5, 0, Math.PI * 2);
      ctx.fillStyle = coreGlow;
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
