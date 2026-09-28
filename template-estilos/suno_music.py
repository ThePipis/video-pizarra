"""Generador de música de fondo: usa por defecto el servidor GPU local (Stable Audio Open / MusicGen)
o Suno API como alternativa si SUNO_API_KEY está configurada.

Uso: python suno_music.py "<estilo>" "<título>" audio/music.mp3 [duración_s]
"""
import json, os, sys, time, urllib.request, urllib.error

style = sys.argv[1] if len(sys.argv) > 1 else "upbeat lofi, 110 bpm"
title = sys.argv[2] if len(sys.argv) > 2 else "musica"
out = sys.argv[3] if len(sys.argv) > 3 else "audio/music.mp3"
dur = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0

HOST = os.environ.get("MEDIA_SERVER_HOST", "http://localhost:8000")

def try_local_gpu():
    try:
        req = urllib.request.Request(f"{HOST}/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as res:
            if res.status == 200:
                print(f"[Music Engine] Conectado a servidor GPU {HOST}...")
                payload = json.dumps({"prompt": f"{style}, {title}", "duration_s": dur, "bpm": 110}).encode("utf-8")
                m_req = urllib.request.Request(f"{HOST}/music", data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(m_req, timeout=180) as m_res:
                    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
                    with open(out, "wb") as f:
                        f.write(m_res.read())
                print(f"[Music Engine] LISTO: {out} ({dur}s) generado con IA en la RTX 5070 Ti.")
                return True
    except Exception as e:
        print(f"[Music Engine] Servidor GPU local no disponible ({e}).")
    return False

# Si el servidor GPU local funciona, terminamos aquí
if try_local_gpu():
    sys.exit(0)

# Fallback a Suno API si hay clave
def key():
    if os.environ.get('SUNO_API_KEY'): return os.environ['SUNO_API_KEY']
    f = os.path.expanduser('~/.config/video-pizarra/keys.env')
    if os.path.exists(f):
        for ln in open(f):
            if ln.startswith('SUNO_API_KEY='): return ln.strip().split('=', 1)[1]
    return None

KEY = key()
if not KEY:
    sys.exit(f"No se pudo conectar al servidor multimedia ({HOST}) y no hay SUNO_API_KEY configurada. Asegúrate de que el servidor GPU esté activo o define MEDIA_SERVER_HOST.")

BASE = 'https://api.sunoapi.org'
UA = 'Mozilla/5.0'

def req(path, body=None):
    h = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json', 'User-Agent': UA, 'Accept': 'application/json'}
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method='POST' if body is not None else 'GET')
    return json.loads(urllib.request.urlopen(r, timeout=40).read())

def audio_urls(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and v.startswith('http') and '.mp3' in v: acc.append(v)
            else: audio_urls(v, acc)
    elif isinstance(o, list):
        for x in o: audio_urls(x, acc)
    return acc

print(f"[Suno API] Generando vía Suno: {title}...")
try:
    r = req('/api/v1/generate', {'customMode': True, 'instrumental': True, 'style': style[:990], 'title': title[:90], 'model': 'V4_5', 'callBackUrl': 'https://example.com/cb'})
except urllib.error.HTTPError as e:
    sys.exit(f'Suno rechazó la petición ({e.code}): {e.read()[:300].decode(errors="ignore")}')
if r.get('code') != 200: sys.exit('Suno rechazó la petición: ' + json.dumps(r)[:300])
task = r['data']['taskId']; print('Suno taskId', task)
for i in range(45):
    time.sleep(8)
    try: d = req(f'/api/v1/generate/record-info?taskId={task}')
    except Exception as e: print('poll', e); continue
    st = (d.get('data') or {}).get('status', '?'); urls = audio_urls(d, [])
    print(f'  [{i}] {st} ({len(urls)} audios)')
    if urls and st in ('SUCCESS', 'FIRST_SUCCESS'):
        url = sorted(urls, key=lambda u: 'stream' in u)[0]
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=180).read())
        print('OK', out); sys.exit(0)
sys.exit('Suno no terminó a tiempo')
