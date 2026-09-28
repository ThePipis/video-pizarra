#!/usr/bin/env python3
"""Cliente de audio para Antigravity: conecta con el servidor GPU multimedia para
generar música instrumental (Stable Audio Open / MusicGen), voz rápida (Edge-TTS / Kokoro) y voz clonada (XTTS-v2).

Uso CLI:
  python audio_client.py music "<prompt>" <duracion_s> <out.mp3>
  python audio_client.py tts-fast "<texto>" <out.wav> [--voice es-MX-DaliaNeural]
  python audio_client.py tts-kokoro "<texto>" <out.wav> [--voice em_alex]
  python audio_client.py tts-clone "<texto>" <out.wav> --ref <referencia.wav>
  python audio_client.py align <audio.wav> <out_words.json>
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_HOST = os.environ.get("MEDIA_SERVER_HOST", "http://localhost:8000")

def is_server_online(host=DEFAULT_HOST, timeout=2):
    try:
        req = urllib.request.Request(f"{host}/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status == 200
    except Exception:
        return False

def generate_music_remote(prompt, duration_s, out_file, bpm=110, steps=48, host=DEFAULT_HOST):
    print(f"[AudioClient] Generando música con Stable Audio Open en {host}...")
    print(f"  Prompt: '{prompt}' | Duración: {duration_s}s | BPM: {bpm} | Steps: {steps}")
    payload = json.dumps({"prompt": prompt, "duration_s": float(duration_s), "bpm": int(bpm), "steps": int(steps)}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/music",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        with open(out_file, "wb") as f:
            f.write(res.read())
    print(f"[AudioClient] Música generada exitosamente: {out_file}")

def generate_tts_fast(text, out_file, words_file="audio/words.json", voice="es-MX-DaliaNeural", host=DEFAULT_HOST):
    # Si el servidor está online, lo procesamos allí; de lo contrario, usamos edge-tts local
    if is_server_online(host):
        print(f"[AudioClient] Generando voz rápida vía {host} ({voice})...")
        payload = json.dumps({"text": text, "voice": voice}).encode("utf-8")
        req = urllib.request.Request(f"{host}/tts/fast", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode("utf-8"))
            # Descargar audio
            audio_url = f"{host}{data['audio_url']}"
            os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
            with urllib.request.urlopen(audio_url) as a_res, open(out_file, "wb") as f:
                f.write(a_res.read())
            # Guardar words.json
            if "words" in data and words_file:
                os.makedirs(os.path.dirname(os.path.abspath(words_file)), exist_ok=True)
                with open(words_file, "w", encoding="utf-8") as wf:
                    json.dump(data["words"], wf, ensure_ascii=False, indent=2)
                print(f"[AudioClient] Timestamps guardados en {words_file} ({len(data['words'])} palabras)")
    else:
        print("[AudioClient] Servidor remoto no disponible. Ejecutando Edge-TTS localmente...")
        import asyncio
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
            words = []
            with open(out_file, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        # Convertir 100ns units a segundos
                        s = round(chunk["offset"] / 10_000_000, 3)
                        d = round(chunk["duration"] / 10_000_000, 3)
                        words.append({"w": chunk["text"], "s": s, "e": round(s + d, 3)})
            if words_file and words:
                os.makedirs(os.path.dirname(os.path.abspath(words_file)), exist_ok=True)
                with open(words_file, "w", encoding="utf-8") as wf:
                    json.dump(words, wf, ensure_ascii=False, indent=2)
                print(f"[AudioClient] Timestamps guardados en {words_file} ({len(words)} palabras)")

        asyncio.run(_run())
    print(f"[AudioClient] Voz lista guardada en {out_file}")

def generate_tts_kokoro(text, out_file, words_file="audio/words.json", voice="em_alex", speed=1.0, lang="e", host=DEFAULT_HOST):
    if not is_server_online(host):
        sys.exit(f"[AudioClient Error] Para usar Kokoro-82M se requiere que {host} esté encendido con la RTX 5070 Ti.")
    print(f"[AudioClient] Generando voz con Kokoro-82M en {host} ({voice}, speed={speed})...")
    payload = json.dumps({"text": text, "voice": voice, "speed": float(speed), "lang": lang}).encode("utf-8")
    req = urllib.request.Request(f"{host}/tts/kokoro", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.loads(res.read().decode("utf-8"))
        audio_url = f"{host}{data['audio_url']}"
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        with urllib.request.urlopen(audio_url) as a_res, open(out_file, "wb") as f:
            f.write(a_res.read())
        if "words" in data and words_file:
            os.makedirs(os.path.dirname(os.path.abspath(words_file)), exist_ok=True)
            with open(words_file, "w", encoding="utf-8") as wf:
                json.dump(data["words"], wf, ensure_ascii=False, indent=2)
            print(f"[AudioClient] Timestamps guardados en {words_file} ({len(data['words'])} palabras)")
    print(f"[AudioClient] Voz Kokoro guardada en {out_file}")

def generate_tts_clone(text, ref_audio, out_file, words_file="audio/words.json", lang="es", host=DEFAULT_HOST):
    if not is_server_online(host):
        sys.exit(f"[AudioClient Error] Para clonar voz con XTTS-v2 se requiere que {host} esté encendido con la RTX 5070 Ti.")
    
    print(f"[AudioClient] Clonando voz en {host} con referencia '{ref_audio}'...")
    import mimetypes
    # Enviar multipart form data con audio de referencia y texto
    boundary = "----AntigravityBoundary" + os.urandom(8).hex()
    body = bytearray()
    
    # Campo text
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\n{text}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{lang}\r\n".encode("utf-8"))
    
    # Archivo ref_audio
    filename = os.path.basename(ref_audio)
    mime = mimetypes.guess_type(ref_audio)[0] or "audio/wav"
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"ref_file\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8"))
    with open(ref_audio, "rb") as rf:
        body.extend(rf.read())
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    req = urllib.request.Request(
        f"{host}/tts/clone",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        data = json.loads(res.read().decode("utf-8"))
        audio_url = f"{host}{data['audio_url']}"
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        with urllib.request.urlopen(audio_url) as a_res, open(out_file, "wb") as f:
            f.write(a_res.read())
        if "words" in data and words_file:
            os.makedirs(os.path.dirname(os.path.abspath(words_file)), exist_ok=True)
            with open(words_file, "w", encoding="utf-8") as wf:
                json.dump(data["words"], wf, ensure_ascii=False, indent=2)
            print(f"[AudioClient] Timestamps (Whisper) guardados en {words_file} ({len(data['words'])} palabras)")
    print(f"[AudioClient] Voz clonada generada exitosamente: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Cliente de Audio Antigravity")
    subparsers = parser.add_subparsers(dest="command")

    # music
    p_music = subparsers.add_parser("music")
    p_music.add_argument("prompt", help="Prompt para Stable Audio Open")
    p_music.add_argument("duration", type=float, help="Duración en segundos")
    p_music.add_argument("output", help="Ruta del archivo de salida (mp3/wav)")
    p_music.add_argument("--bpm", type=int, default=110, help="Tempo en BPM")
    p_music.add_argument("--steps", type=int, default=48, help="Pasos de difusión (default 48 para ~35s)")
    p_music.add_argument("--host", default=DEFAULT_HOST, help="URL del servidor")

    # tts-fast
    p_fast = subparsers.add_parser("tts-fast")
    p_fast.add_argument("text", help="Texto a narrar")
    p_fast.add_argument("output", help="Archivo de audio destino")
    p_fast.add_argument("--voice", default="es-MX-DaliaNeural", help="Voz Edge-TTS")
    p_fast.add_argument("--words", default="audio/words.json", help="Destino de words.json")
    p_fast.add_argument("--host", default=DEFAULT_HOST, help="URL del servidor")

    # tts-kokoro
    p_kokoro = subparsers.add_parser("tts-kokoro")
    p_kokoro.add_argument("text", help="Texto a narrar con Kokoro-82M")
    p_kokoro.add_argument("output", help="Archivo de audio destino")
    p_kokoro.add_argument("--voice", default="em_alex", help="Voz Kokoro (ej: em_alex, ef_dora)")
    p_kokoro.add_argument("--speed", type=float, default=1.0, help="Velocidad de locución")
    p_kokoro.add_argument("--lang", default="e", help="Código de idioma Kokoro ('e' = español)")
    p_kokoro.add_argument("--words", default="audio/words.json", help="Destino de words.json")
    p_kokoro.add_argument("--host", default=DEFAULT_HOST, help="URL del servidor")

    # tts-clone
    p_clone = subparsers.add_parser("tts-clone")
    p_clone.add_argument("text", help="Texto a narrar con voz clonada")
    p_clone.add_argument("output", help="Archivo de audio destino")
    p_clone.add_argument("--ref", required=True, help="Audio de referencia (5-10s)")
    p_clone.add_argument("--lang", default="es", help="Código de idioma")
    p_clone.add_argument("--words", default="audio/words.json", help="Destino de words.json")
    p_clone.add_argument("--host", default=DEFAULT_HOST, help="URL del servidor")

    args = parser.parse_args()
    if args.command == "music":
        generate_music_remote(args.prompt, args.duration, args.output, bpm=args.bpm, steps=args.steps, host=args.host)
    elif args.command == "tts-fast":
        generate_tts_fast(args.text, args.output, words_file=args.words, voice=args.voice, host=args.host)
    elif args.command == "tts-kokoro":
        generate_tts_kokoro(args.text, args.output, words_file=args.words, voice=args.voice, speed=args.speed, lang=args.lang, host=args.host)
    elif args.command == "tts-clone":
        generate_tts_clone(args.text, args.ref, args.output, words_file=args.words, lang=args.lang, host=args.host)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
