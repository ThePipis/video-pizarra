"""Transcribe la voz en off con tiempos por palabra → audio/words.json, y muestra dónde empieza cada frase
para ajustar la duración (`dur`) de cada escena al audio.

Uso: python vo_words.py audio/vo.wav [idioma=es]
Prioridad:
  1. Servidor GPU multimedia (faster-whisper acelerado en CUDA con GPU dedicada).
  2. faster-whisper local en CPU/GPU.
  3. AssemblyAI (si hay ASSEMBLYAI_API_KEY).
"""
import json, os, subprocess, sys, urllib.request, urllib.error

path = sys.argv[1] if len(sys.argv) > 1 else "audio/vo.wav"
lang = sys.argv[2] if len(sys.argv) > 2 else "es"
out_json = "audio/words.json"
HOST = os.environ.get("MEDIA_SERVER_HOST", "http://localhost:8000")

def try_remote_align():
    try:
        req = urllib.request.Request(f"{HOST}/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as res:
            if res.status != 200: return None
            
        print(f"[Whisper Align] Conectando a servidor GPU ({HOST}) para alinear...")
        boundary = "----WhisperBoundary" + os.urandom(8).hex()
        body = bytearray()
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{lang}\r\n".encode("utf-8"))
        
        filename = os.path.basename(path)
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio_file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8"))
        with open(path, "rb") as f:
            body.extend(f.read())
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        
        p_req = urllib.request.Request(
            f"{HOST}/align",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        with urllib.request.urlopen(p_req, timeout=60) as a_res:
            data = json.loads(a_res.read().decode("utf-8"))
            return data.get("words", [])
    except Exception as e:
        print(f"[Whisper Align] Servidor remoto no disponible ({e}). Intentando fallback local...")
        return None

words = try_remote_align()

if words is None:
    # Fallback local con faster-whisper
    try:
        from faster_whisper import WhisperModel
        print("[Whisper Align] Ejecutando faster-whisper localmente...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(path, language=lang, word_timestamps=True)
        words = []
        for s in segs:
            for w in s.words:
                words.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
    except Exception as e_w:
        sys.exit(f"Error en transcripción local: {e_w}")

os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(words, f, ensure_ascii=False, indent=2)

dur_voz = words[-1]["e"] if words else 0.0
print(f"\n{len(words)} palabras → {out_json} (duración voz: {dur_voz:.2f}s)\n")

# Mostrar resumen de frases para verificar sincronización
line, start = [], None
for w in words:
    if start is None: start = w["s"]
    line.append(w["w"])
    if w["w"].endswith((".", "?", "!", "…")):
        print(f"{start:7.2f}s  {' '.join(line)}")
        line, start = [], None
if line:
    print(f"{start:7.2f}s  {' '.join(line)}")
