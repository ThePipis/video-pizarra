// Estilo Cyber Dark Tech / Neon Architecture
// Fondo oscuro obsidiana, cuadrícula técnica animada, resplandor neón cian/ámbar y paneles glassmorphism.
import * as L from '../engine/lib.js';
import { BASE, title, para, layoutRich, drawRich, drawFrame } from '../engine/base.js';

const BG = '#0B0F19', BG_GRAD = '#0F172A';
const INK = '#F8FAFC', MUTED = '#94A3B8';
const CYAN = '#00F2FE', AMBER = '#F59E0B', LINE = 'rgba(56, 189, 248, 0.14)';
const SLOW = t => 1 - Math.pow(1 - t, 4);

function neonGlow(ctx, x, y, w, h, col, p, u) {
  if (p <= 0) return;
  ctx.save();
  const ww = w * L.E.out(p);
  // Halo difuso
  ctx.shadowColor = col;
  ctx.shadowBlur = 18 * u;
  ctx.fillStyle = col + '33';
  ctx.fillRect(x - 4 * u, y + h * 0.25, ww + 8 * u, h * 0.65);
  // Barra luminosa inferior
  ctx.shadowBlur = 10 * u;
  ctx.fillStyle = col;
  ctx.fillRect(x, y + h * 0.9, ww, 3 * u);
  ctx.restore();
}

function techPanel(ctx, b, col, fillCol, u, p = 1) {
  if (p <= 0) return;
  ctx.save();
  ctx.globalAlpha = L.clamp(p * 1.4);
  // Sombra y brillo
  ctx.shadowColor = col + '40';
  ctx.shadowBlur = 24 * u;
  // Fondo glassmorphism
  L.rrect(ctx, b.x, b.y, b.w, b.h, 12 * u);
  ctx.fillStyle = fillCol || 'rgba(15, 23, 42, 0.78)';
  ctx.fill();
  // Borde técnico fino
  ctx.shadowBlur = 6 * u;
  ctx.strokeStyle = col;
  ctx.lineWidth = 1.4 * u;
  ctx.stroke();
  // Pequeños acentos en las esquinas superiores (marcas HUD)
  const len = 10 * u;
  ctx.lineWidth = 2.4 * u;
  ctx.beginPath();
  ctx.moveTo(b.x, b.y + len); ctx.lineTo(b.x, b.y); ctx.lineTo(b.x + len, b.y);
  ctx.moveTo(b.x + b.w - len, b.y); ctx.lineTo(b.x + b.w, b.y); ctx.lineTo(b.x + b.w, b.y + len);
  ctx.stroke();
  ctx.restore();
}

export default {
  id: 'cyber-tech',
  name: 'Cyber Dark Tech / Neon',
  fonts: 'Syne:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600',
  fontLoads: [
    '600 60px "Syne"', '700 60px "Syne"', '800 60px "Syne"',
    '400 30px "Inter"', '500 30px "Inter"', '600 30px "Inter"',
    '400 20px "JetBrains Mono"', '600 20px "JetBrains Mono"'
  ],
  palette: {
    bg: BG, ink: INK, accent: CYAN, secondary: AMBER,
    muted: MUTED, panel: 'rgba(15, 23, 42, 0.85)',
    line: LINE, good: '#10B981', bad: '#EF4444', mascot: CYAN
  },
  type: {
    display: s => `700 ${s}px "Syne"`,
    em: s => `800 ${s}px "Syne"`,
    body: s => `400 ${s}px "Inter"`,
    bodyEm: s => `600 ${s}px "Inter"`,
    label: s => `600 ${s}px "JetBrains Mono"`,
    mono: s => `400 ${s}px "JetBrains Mono"`,
    thin: s => `600 ${s}px "Syne"`,
    semi: s => `700 ${s}px "Syne"`
  },
  ls: -0.02,
  lh: 1.05,
  sfx: 'digital',
  transDur: 0.65,
  push: 0.02,
  music: 'cyber ambient tech lo-fi, subtle synth arpeggios, warm sub-bass, clean electronic beat, 95 BPM, focused and futuristic, instrumental',

  background(K, s) {
    const { ctx, W, H, u } = K;
    // Gradiente de fondo obsidiana
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, BG);
    g.addColorStop(1, BG_GRAD);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    // Grid técnico suave
    const step = 90 * u;
    ctx.strokeStyle = LINE;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = step; x < W; x += step) {
      ctx.moveTo(x, 0); ctx.lineTo(x, H);
    }
    for (let y = step; y < H; y += step) {
      ctx.moveTo(0, y); ctx.lineTo(W, y);
    }
    ctx.stroke();

    // Puntos luminosos en intersecciones con leve pulso
    ctx.fillStyle = 'rgba(0, 242, 254, 0.35)';
    const pulse = 0.8 + 0.3 * Math.sin(K.t * 3);
    for (let x = step * 2; x < W; x += step * 3) {
      for (let y = step * 2; y < H; y += step * 2) {
        ctx.beginPath();
        ctx.arc(x, y, 1.8 * u * pulse, 0, 7);
        ctx.fill();
      }
    }

    // HUD Header superior
    const m = 80 * u, yTop = K.vertical ? 90 * u : 65 * u;
    const lp = SLOW(L.clamp(s.t / 1.0));
    // Línea neón superior
    ctx.fillStyle = 'rgba(0, 242, 254, 0.3)';
    ctx.fillRect(m, yTop, (W - 2 * m) * lp, 1.5 * u);
    // Badge de escena [01 // 08]
    const idx = `[ ARCH // ${(s.i + 1).toString().padStart(2, '0')} ]`;
    L.text(ctx, idx, m, yTop - 16 * u, { font: K.S.type.label(15 * u), color: CYAN, alpha: lp });
    // Status LED
    ctx.fillStyle = '#10B981';
    ctx.shadowColor = '#10B981';
    ctx.shadowBlur = 8 * u;
    ctx.beginPath();
    ctx.arc(W - m - 6 * u, yTop - 20 * u, 4 * u * lp, 0, 7);
    ctx.fill();
    ctx.shadowBlur = 0;
  },

  headline(K, str, box, p, s, o = {}) {
    const ctx = K.ctx, u = K.u;
    const top = (K.vertical ? 130 : 100) * u;
    if (box.y < top) box = { ...box, y: top, h: box.h - (top - box.y) };

    const R = layoutRich(ctx, K.rich(str), box, {
      font: sz => K.S.type.display(sz),
      emFont: sz => K.S.type.em(sz),
      max: (o.size === 'm' ? 100 : 160) * u,
      min: 24 * u,
      lh: 1.06
    });

    const n = R.lines.length, y0 = box.y + (box.h - n * R.lh) / 2;
    let wi = 0;
    R.lines.forEach((line, i) => {
      const x0 = o.align === 'center' ? box.x + (box.w - R.widths[i]) / 2 : box.x;
      line.forEach(t => {
        if (t.em) {
          neonGlow(ctx, x0 + t.x, y0 + i * R.lh, t.width, R.size, CYAN, L.clamp(p * 1.5 - 0.4), u);
        }
        wi++;
      });
    });

    drawRich(K, R, box, SLOW(p), {
      align: o.align,
      color: INK,
      emColor: CYAN,
      reveal: 'rise'
    });
  },

  text(K, str, box, p, role, s, o = {}) {
    const top = (K.vertical ? 130 : 100) * K.u;
    if (box.y < top) box = { ...box, y: top, h: box.h - (top - box.y) };

    if (role === 'kicker' || role === 'label') {
      const tag = str.startsWith('[') ? str : `[ ${str.toUpperCase()} ]`;
      return para(K, tag, box, p, {
        font: sz => K.S.type.label(sz),
        color: CYAN,
        ls: 0.12,
        max: 20,
        align: o.align || 'left'
      });
    }

    if (role === 'headGood' || role === 'headBad') {
      const col = role === 'headGood' ? CYAN : AMBER;
      return title(K, str, box, p, {
        color: col,
        max: 56,
        reveal: 'rise',
        font: sz => K.S.type.semi(sz)
      });
    }

    return BASE.text(K, str, box, p, role, s, {
      color: role === 'bad' ? '#64748B' : role === 'body' ? '#CBD5E1' : INK,
      font: role === 'item' || role === 'step' ? (sz => K.S.type.display(sz)) : undefined,
      max: role === 'item' ? 52 : role === 'step' ? 44 : 44,
      ...o
    });
  },

  panel(K, b, p, s, kind) {
    if (p <= 0) return;
    const { ctx, u } = K;
    const col = kind === 'good' ? CYAN : kind === 'bad' ? AMBER : 'rgba(56, 189, 248, 0.4)';
    const fill = kind === 'good' ? 'rgba(12, 74, 110, 0.28)' : kind === 'bad' ? 'rgba(120, 53, 15, 0.28)' : 'rgba(15, 23, 42, 0.82)';
    techPanel(ctx, b, col, fill, u, SLOW(p));
  },

  bullet(K, i, b, p, s) {
    if (p <= 0) return;
    const { ctx, u } = K;
    const [cx, cy] = L.center(b);
    const r = Math.min(b.w, b.h) * 0.45;
    const e = SLOW(p);

    ctx.save();
    ctx.shadowColor = CYAN;
    ctx.shadowBlur = 10 * u;
    ctx.fillStyle = 'rgba(0, 242, 254, 0.15)';
    ctx.beginPath();
    ctx.arc(cx, cy, r * e, 0, 7);
    ctx.fill();

    ctx.strokeStyle = CYAN;
    ctx.lineWidth = 1.8 * u;
    ctx.stroke();

    ctx.shadowBlur = 0;
    const num = (i + 1).toString().padStart(2, '0');
    L.text(ctx, num, cx, cy + r * 0.35, {
      font: K.S.type.label(r * 0.9),
      color: INK,
      align: 'center',
      alpha: e
    });
    ctx.restore();
  },

  number(K, str, box, p, s, o) {
    const ctx = K.ctx, u = K.u;
    const R = layoutRich(ctx, K.rich(str), box, {
      font: sz => K.S.type.display(sz),
      max: (o?.small ? 110 : 300) * u,
      min: 24 * u,
      lh: 1
    });

    const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
    if (!o?.small) {
      neonGlow(ctx, cx - R.widths[0] / 2 - 20 * u, cy - R.size * 0.1, R.widths[0] + 40 * u, R.size * 0.6, CYAN, p, u);
    }
    drawRich(K, R, box, SLOW(p), {
      align: 'center',
      color: o?.small ? CYAN : INK,
      emColor: CYAN,
      reveal: 'rise'
    });
  },

  prompt(K, str, box, p, s, tp) {
    if (p <= 0) return;
    const { ctx, u } = K;
    techPanel(ctx, box, 'rgba(0, 242, 254, 0.45)', 'rgba(10, 15, 30, 0.9)', u, SLOW(p));
    L.text(ctx, '>_ ATTENTION_INPUT', box.x + 16 * u, box.y + 22 * u, {
      font: K.S.type.label(14 * u),
      color: CYAN,
      alpha: p
    });
    const visStr = str.slice(0, Math.ceil(str.length * tp)) + (tp < 1 || (K.frame >> 3) % 2 ? ' █' : '');
    para(K, visStr, { x: box.x + 16 * u, y: box.y + 30 * u, w: box.w - 32 * u, h: box.h - 40 * u }, 1, {
      font: sz => K.S.type.mono(sz),
      color: INK,
      max: 34,
      valign: 'middle'
    });
  },

  button(K, str, b, p) {
    if (p <= 0) return;
    const { ctx, u } = K, e = SLOW(p);
    ctx.save();
    ctx.globalAlpha = L.clamp(p * 1.5);
    ctx.shadowColor = CYAN;
    ctx.shadowBlur = 18 * u;
    L.rrect(ctx, b.x, b.y, b.w, b.h, 8 * u);
    ctx.fillStyle = CYAN;
    ctx.fill();
    ctx.restore();
    para(K, str, L.inset(b, b.h * 0.3, b.h * 0.2), e, {
      font: sz => K.S.type.label(sz),
      color: '#0B0F19',
      max: 26,
      align: 'center'
    });
  },

  caption(K, words, act, box, p) {
    const { ctx, u } = K;
    ctx.save();
    ctx.globalAlpha = p;
    ctx.font = K.S.type.bodyEm(30 * u);
    const w = ctx.measureText(words.join(' ')).width;
    let cx = box.x + (box.w - w) / 2;

    // Caja glassmorphism para subtítulos
    ctx.shadowColor = 'rgba(0, 242, 254, 0.2)';
    ctx.shadowBlur = 14 * u;
    ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
    L.rrect(ctx, cx - 24 * u, box.y + box.h * 0.1, w + 48 * u, box.h * 0.8, 10 * u);
    ctx.fill();
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.35)';
    ctx.lineWidth = 1 * u;
    ctx.stroke();
    ctx.shadowBlur = 0;

    words.forEach((wd, i) => {
      ctx.fillStyle = i === act ? CYAN : i < act ? INK : '#64748B';
      if (i === act) {
        ctx.shadowColor = CYAN;
        ctx.shadowBlur = 8 * u;
      } else {
        ctx.shadowBlur = 0;
      }
      ctx.fillText(wd, cx, box.y + box.h * 0.63);
      cx += ctx.measureText(wd + ' ').width;
    });
    ctx.restore();
  },

  mascot(K, box, p, s, mood) {
    if (p <= 0) return;
    const { ctx, u } = K;
    ctx.save();
    ctx.globalAlpha = L.clamp(p * 1.6);
    ctx.shadowColor = CYAN;
    ctx.shadowBlur = 24 * u;
    L.mascot(ctx, K.spec.mascot, { ...box, y: box.y + (1 - SLOW(p)) * 20 * u }, {
      color: '#1E293B',
      outline: CYAN,
      eye: CYAN,
      eyeStyle: mood === 'happy' ? 'happy' : 'dot',
      bob: Math.sin(K.t * 2.2) * 4 * u
    });
    ctx.restore();
  },

  transition(K, A, B, p, info) {
    const { ctx, W, H, u } = K;
    const r = SLOW(info.raw);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, W, H);
    // Efecto de barrido de haz neón horizontal
    ctx.save();
    ctx.globalAlpha = 1 - L.clamp(info.raw * 1.5);
    ctx.drawImage(A, 0, 0);
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = L.clamp(info.raw * 1.5 - 0.2);
    ctx.drawImage(B, 0, 0);
    ctx.restore();

    // Línea de escaneo láser luminosa que viaja de izquierda a derecha
    const xScan = W * r;
    ctx.save();
    ctx.shadowColor = CYAN;
    ctx.shadowBlur = 20 * u;
    ctx.fillStyle = CYAN;
    ctx.fillRect(xScan - 2 * u, 0, 4 * u, H);
    ctx.restore();
  }
};
