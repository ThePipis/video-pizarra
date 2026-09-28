// Deterministic renderer: calls window.renderAt(t) per frame, grabs the canvas as JPEG, pipes to ffmpeg.
//   node render.mjs out.mp4                 full video (silent) + sfx.json
//   node render.mjs --scenes                one QA still per scene → stills/
//   node render.mjs --stills 1.2,5,9.8      stills at given seconds → stills/
//   node render.mjs --every 1               a still every N seconds → stills/
//   --query "style=noir&format=9:16"        URL overrides (style, format, spec)
//   --outdir dir                            where stills go (default stills/)
//   --from 3 --to 8                         render only that time range (clips/previews)
//   --workers 8                             parallel pages for the video (default min(8, cores/2); 1 = old serial path)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir, readdir, unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir, cpus } from 'node:os';
import { extname, join } from 'node:path';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const has = k => args.includes(k);
const out = args[0] && !args[0].startsWith('--') ? args[0] : null;
const root = process.cwd(), q = opt('--query', ''), outdir = opt('--outdir', 'stills');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try { const p = join(root, decodeURIComponent(req.url.split('?')[0])); const b = await readFile(p); res.writeHead(200, { 'content-type': types[extname(p).toLowerCase()] || 'application/octet-stream' }); res.end(b); }
  catch { res.writeHead(404); res.end(); }
}).listen(0);
// Use CHROME_PATH, else Playwright's default, else any headless shell already downloaded (version mismatch-safe)
async function launch() {
  if (process.env.CHROME_PATH) return chromium.launch({ executablePath: process.env.CHROME_PATH });
  try { return await chromium.launch(); } catch (e) {
    const base = process.platform === 'darwin'
      ? join(homedir(), 'Library/Caches/ms-playwright')
      : process.platform === 'win32'
        ? (process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'ms-playwright') : join(homedir(), 'AppData', 'Local', 'ms-playwright'))
        : join(homedir(), '.cache/ms-playwright');
    const dirs = existsSync(base) ? (await readdir(base)).filter(d => d.startsWith('chromium')).sort().reverse() : [];
    for (const d of dirs) for (const sub of [
      'chrome-headless-shell-win64/chrome-headless-shell.exe',
      'chrome-win64/chrome.exe',
      'chrome-headless-shell-mac-arm64/chrome-headless-shell',
      'chrome-headless-shell-mac-x64/chrome-headless-shell',
      'chrome-headless-shell-linux64/chrome-headless-shell',
      'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
      'chrome-linux64/chrome'
    ]) {
      const exe = join(base, d, sub); if (existsSync(exe)) return chromium.launch({ executablePath: exe });
    }
    throw new Error('No encontré Chromium. Corre: npx playwright install chromium');
  }
}
const browser = await launch();
let fatal = null;
// each page gets its own context → its own renderer process (so workers really run in parallel)
async function openPage() {
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })).newPage();
  page.on('pageerror', e => { console.error('PAGE ERROR', e.message); if (!fatal) fatal = e; });
  page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  await page.goto(`http://localhost:${server.address().port}/index.html?${q}`);
  for (let i = 0; ; i++) { // wait for READY, but stop at the first page error
    if (await page.evaluate(() => window.READY === true)) break;
    if (fatal) { console.error('El video no pudo cargar (revisa el error de arriba: suele ser una coma/comilla en video.js o una ruta de imagen).'); await browser.close(); server.close(); process.exit(1); }
    if (i > 1200) { console.error('Timeout esperando la página'); process.exit(1); }
    await new Promise(r => setTimeout(r, 100));
  }
  return page;
}
const page = await openPage();
const duration = await page.evaluate(() => window.DURATION), fps = Number(opt('--fps', await page.evaluate(() => window.K.fps)));
const grab = async (t, quality = 0.9, pg = page) => Buffer.from((await pg.evaluate(([t, q]) => { window.renderAt(t); return document.getElementById('stage').toDataURL('image/jpeg', q).split(',')[1]; }, [t, quality])), 'base64');

let stills = opt('--stills') ? opt('--stills').split(',').map(Number) : null;
if (opt('--every')) { stills = []; for (let x = 0.4; x < duration; x += Number(opt('--every'))) stills.push(+x.toFixed(2)); }
if (has('--scenes')) stills = (await page.evaluate(() => window.SCENES)).map(s => +(s.start + Math.min(s.dur * 0.8, 2.6)).toFixed(2));
if (stills) {
  await mkdir(outdir, { recursive: true });
  for (const t of stills) await writeFile(`${outdir}/s_${t.toFixed(2).padStart(6, '0')}.jpg`, await grab(t, 0.85));
  console.log(`stills: ${stills.length} → ${outdir}/  (duración ${duration.toFixed(2)}s)`);
} else {
  const file = out || 'video.mp4';
  await writeFile('sfx.json', JSON.stringify({ events: await page.evaluate(() => window.SFX), style: await page.evaluate(() => window.STYLE), duration }));
  const t0s = Number(opt('--from', 0)), t1s = Math.min(duration, Number(opt('--to', duration)));
  const frames = Math.ceil((t1s - t0s) * fps);
  // renderAt(t) is pure in t → split the frames into contiguous chunks, one page + one ffmpeg each, then concat
  const workers = Math.max(1, Math.min(Number(opt('--workers', Math.min(8, Math.floor(cpus().length / 2)))), frames));
  const chunk = Math.ceil(frames / workers), parts = [], t0 = Date.now(); let done = 0;
  const encode = (dst) => spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', dst], { stdio: ['pipe', 'inherit', 'inherit'] });
  console.log(`${frames} frames con ${workers} worker(s)`);
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const f0 = w * chunk, f1 = Math.min(frames, f0 + chunk); if (f0 >= f1) return;
    const dst = workers === 1 ? file : `_part_${w}.mp4`; parts[w] = dst;
    const pg = w === 0 ? page : await openPage(), ff = encode(dst);
    for (let f = f0; f < f1; f++) {
      const buf = await grab(t0s + f / fps, 0.92, pg);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (++done % 150 === 0) console.log(`frame ${done}/${frames} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
    ff.stdin.end(); await new Promise((r, rej) => ff.on('close', c => c === 0 ? r() : rej(new Error(`ffmpeg falló en worker ${w}`))));
  }));
  if (workers > 1) {
    const list = parts.filter(Boolean);
    await writeFile('_parts.txt', list.map(p => `file '${p}'`).join('\n'));
    const cat = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', '_parts.txt', '-c', 'copy', '-movflags', '+faststart', file], { stdio: 'inherit' });
    await new Promise((r, rej) => cat.on('close', c => c === 0 ? r() : rej(new Error('ffmpeg concat falló'))));
    for (const p of [...list, '_parts.txt']) await unlink(p).catch(() => {});
  }
  console.log('listo', file, duration.toFixed(2) + 's', `en ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
await browser.close(); server.close();
