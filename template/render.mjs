// Deterministic multi-worker renderer: seeks the GSAP timeline, screenshots the SVG, pipes JPEGs to ffmpeg.
//   node render.mjs out.mp4 [--fps 30] [--mode A] [--workers 4]   full video (no audio)
//   node render.mjs --every 1.5                                   QA stills every 1.5 s → stills/
//   node render.mjs --stills 3.2,10,24.5                          QA stills at given seconds → stills/
// Also writes sfx.json (sound events) and hits.json (transition hits) for the audio mix.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir, readdir, unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir, cpus } from 'node:os';
import { extname, join } from 'node:path';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const out = args[0] && !args[0].startsWith('--') ? args[0] : null;
const isDraft = args.includes('--draft');
const fps = Number(opt('--fps', isDraft ? 24 : 30)), mode = opt('--mode', 'A');
const numWorkers = Math.max(1, Math.min(Number(opt('--workers', 6)), (cpus() || []).length || 6));
const root = process.cwd();
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg' };

const server = createServer(async (req, res) => {
  try {
    const p = join(root, decodeURIComponent(req.url.split('?')[0]));
    const data = await readFile(p);
    res.writeHead(200, { 'content-type': types[extname(p)] || 'application/octet-stream' });
    res.end(data);
  } catch { res.writeHead(404); res.end(); }
}).listen(0);

async function launch() {
  const flags = ['--enable-gpu', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'];
  if (process.env.CHROME_PATH) return chromium.launch({ executablePath: process.env.CHROME_PATH, args: flags });
  try { return await chromium.launch({ args: flags }); } catch (e) {
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
      const exe = join(base, d, sub); if (existsSync(exe)) return chromium.launch({ executablePath: exe, args: flags });
    }
    throw new Error('No encontré Chromium. Corre: npx playwright install chromium');
  }
}

const browser = await launch();
const pageUrl = `http://localhost:${server.address().port}/index.html?render=1&mode=${mode}`;
const probePage = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
probePage.on('pageerror', e => console.error('PAGE ERROR', e.message));
await probePage.goto(pageUrl);
await probePage.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
let [vw, vh] = await probePage.evaluate(() => [window.VW, window.VH]);
if (isDraft) {
  vw = Math.round(vw * 0.6666);
  vh = Math.round(vh * 0.6666);
}
await probePage.setViewportSize({ width: vw, height: vh });
const duration = await probePage.evaluate(() => window.DURATION);
await writeFile('sfx.json', JSON.stringify(await probePage.evaluate(() => window.SFX || [])));
await writeFile('hits.json', JSON.stringify(await probePage.evaluate(() => window.HITS || [])));

let stills = opt('--stills') ? opt('--stills').split(',').map(Number) : null;
if (opt('--every')) { stills = []; for (let x = 0.3; x < duration; x += Number(opt('--every'))) stills.push(+x.toFixed(2)); }
if (stills) {
  const svg = await probePage.$('#stage');
  await mkdir('stills', { recursive: true });
  for (const t of stills) {
    await probePage.evaluate(t => window.renderAt(t), t);
    await writeFile(`stills/s_${t.toFixed(2).padStart(6, '0')}.jpg`, await svg.screenshot({ type: 'jpeg', quality: 85 }));
  }
  console.log(`stills done (${stills.length}), duration ${duration.toFixed(2)}s`);
} else {
  const file = out || 'video.mp4';
  const totalFrames = Math.ceil(duration * fps);
  const t0 = Date.now();

  if (numWorkers <= 1) {
    const svg = await probePage.$('#stage');
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let f = 0; f < totalFrames; f++) {
      await probePage.evaluate(t => window.renderAt(t), f / fps);
      const buf = await svg.screenshot({ type: 'jpeg', quality: 92 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 200 === 0) console.log(`frame ${f}/${totalFrames} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  } else {
    const chunkSize = Math.ceil(totalFrames / numWorkers);
    const partFiles = [];
    const workerPromises = [];
    let completedFrames = 0;

    console.log(`Renderizando ${totalFrames} frames en paralelo con ${numWorkers} workers...`);

    for (let w = 0; w < numWorkers; w++) {
      const fStart = w * chunkSize;
      const fEnd = Math.min(totalFrames, (w + 1) * chunkSize);
      if (fStart >= totalFrames) continue;

      const partFile = `_part_${w}.mp4`;
      partFiles.push(partFile);

      workerPromises.push((async () => {
        const ctx = (w === 0) ? null : await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1 });
        const page = (w === 0) ? probePage : await ctx.newPage();
        if (w > 0) {
          page.on('pageerror', e => console.error(`WORKER ${w} PAGE ERROR`, e.message));
          await page.goto(pageUrl);
          await page.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
        }
        const svg = await page.$('#stage');
        const ff = spawn('ffmpeg', [
          '-y', '-loglevel', 'error',
          '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
          '-pix_fmt', 'yuv420p', partFile
        ], { stdio: ['pipe', 'inherit', 'inherit'] });

        for (let f = fStart; f < fEnd; f++) {
          await page.evaluate(t => window.renderAt(t), f / fps);
          const buf = await svg.screenshot({ type: 'jpeg', quality: 92 });
          if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
          completedFrames++;
          if (completedFrames % 250 === 0) {
            const elapsed = ((Date.now() - t0) / 1000).toFixed(0);
            const fpsCurr = (completedFrames / ((Date.now() - t0) / 1000)).toFixed(1);
            console.log(`Progreso: ${completedFrames}/${totalFrames} frames (${elapsed}s, ${fpsCurr} FPS)`);
          }
        }
        ff.stdin.end();
        await new Promise((r, rej) => { ff.on('close', code => code === 0 ? r() : rej(new Error(`worker ${w} ffmpeg error`))); });
        if (w > 0) {
          await page.close();
          await ctx.close();
        }
      })());
    }

    await Promise.all(workerPromises);

    console.log(`Uniendo ${partFiles.length} partes en ${file}...`);
    const listFile = `_parts_${Date.now()}.txt`;
    const listContent = partFiles.map(f => `file '${f}'`).join('\n');
    await writeFile(listFile, listContent);

    await new Promise((resolve, reject) => {
      const concatFf = spawn('ffmpeg', [
        '-y', '-loglevel', 'error',
        '-f', 'concat', '-safe', '0', '-i', listFile,
        '-c', 'copy', '-movflags', '+faststart', file
      ], { stdio: ['inherit', 'inherit', 'inherit'] });
      concatFf.on('close', code => code === 0 ? resolve() : reject(new Error('ffmpeg concat failed')));
    });

    for (const f of partFiles) await unlink(f).catch(() => {});
    await unlink(listFile).catch(() => {});
  }

  const elapsedTotal = ((Date.now() - t0) / 1000).toFixed(1);
  const totalFps = (totalFrames / ((Date.now() - t0) / 1000)).toFixed(1);
  console.log(`done ${file} (${duration.toFixed(2)}s) en ${elapsedTotal}s a ${totalFps} FPS total`);
}

await browser.close();
server.close();
