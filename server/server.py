import os
import gc
import uuid
import json
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

# Forzar todas las cachés a /srv para no saturar la partición raíz /
BASE_DIR = Path("/srv/builds/video-pizarra-server")
os.environ["HF_HOME"] = str(BASE_DIR / "hf_cache")
os.environ["TORCH_HOME"] = str(BASE_DIR / "torch_cache")
os.environ["COQUI_TOS_AGREED"] = "1"

import torch
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MUSICGEN_MIN_VRAM_GB = float(os.environ.get("MUSICGEN_MIN_VRAM_GB", "1.2"))

OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Antigravity Media Engine Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

def free_gpu():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

@app.get("/health")
def health():
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None"
    free_bytes, total_bytes = torch.cuda.mem_get_info() if torch.cuda.is_available() else (0, 0)
    return {
        "status": "online",
        "gpu": gpu_name,
        "vram_free_gb": round(free_bytes / (1024**3), 2),
        "vram_total_gb": round(total_bytes / (1024**3), 2),
        "cuda_version": torch.version.cuda,
    }

class MusicRequest(BaseModel):
    prompt: str
    duration_s: float = 45.0
    bpm: int = 110
    steps: int = 48
    cfg_scale: float = 6.0

@app.post("/music")
def generate_music(req: MusicRequest):
    t_start = time.time()
    job_id = uuid.uuid4().hex[:10]
    out_wav = OUTPUT_DIR / f"music_{job_id}.wav"
    out_mp3 = OUTPUT_DIR / f"music_{job_id}.mp3"
    
    hf_token = os.environ.get("HF_TOKEN", None)
    
    print(f"[Music] Generando música para prompt: '{req.prompt}', dur: {req.duration_s}s, bpm: {req.bpm}, steps: {req.steps}")
    try:
        from diffusers import StableAudioPipeline
        
        model_id = "stabilityai/stable-audio-open-1.0"
        pipe = StableAudioPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            token=hf_token,
            cache_dir=str(BASE_DIR / "hf_cache")
        )
        pipe = pipe.to("cuda")
        
        audio_dur = min(47.0, req.duration_s)
        full_prompt = f"{req.prompt}, {req.bpm} bpm"
        
        output = pipe(
            full_prompt,
            negative_prompt="Low quality, noisy, distorted, speech, vocal",
            num_inference_steps=req.steps,
            audio_end_in_s=audio_dur,
            guidance_scale=req.cfg_scale,
        ).audios[0]
        
        sf.write(str(out_wav), output.T.float().cpu().numpy(), pipe.vae.sampling_rate)
        del pipe
        free_gpu()
        
        if req.duration_s > 45.0:
            loop_wav = OUTPUT_DIR / f"music_{job_id}_loop.wav"
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-stream_loop", "1", "-i", str(out_wav),
                "-t", str(req.duration_s), "-af", f"afade=t=out:st={req.duration_s - 2.5}:d=2.5",
                str(loop_wav)
            ], check=True)
            out_wav = loop_wav
            
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
            "-c:a", "libmp3lame", "-b:a", "256k", str(out_mp3)
        ], check=True)
        
        print(f"[Music] Generación completada con éxito en {time.time() - t_start:.2f}s")
        from fastapi.responses import FileResponse
        return FileResponse(str(out_mp3), media_type="audio/mpeg", filename=f"music_{job_id}.mp3")
        
    except Exception as e:
        free_gpu()
        print(f"[Music Fallback] Stable Audio no disponible ({e}). Intentando MusicGen...")
        
        # Determinar si hay VRAM suficiente para CUDA con float16 (umbral configurable via MUSICGEN_MIN_VRAM_GB)
        free_bytes = torch.cuda.mem_get_info()[0] if torch.cuda.is_available() else 0
        free_gb = round(free_bytes / 1024**3, 2)
        device = "cuda" if free_bytes > MUSICGEN_MIN_VRAM_GB * 1024**3 else "cpu"
        if device == "cpu":
            print(f"[WARNING] MusicGen cayendo a CPU (VRAM libre: {free_gb} GB < umbral {MUSICGEN_MIN_VRAM_GB} GB). Generación será ~6x más lenta.")
        else:
            print(f"[Music Fallback] Dispositivo seleccionado para MusicGen: {device} (VRAM libre: {free_gb} GB)")
        
        try:
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            processor = AutoProcessor.from_pretrained("facebook/musicgen-small", cache_dir=str(BASE_DIR / "hf_cache"))
            dtype = torch.float16 if device == "cuda" else torch.float32
            model = MusicgenForConditionalGeneration.from_pretrained(
                "facebook/musicgen-small", 
                cache_dir=str(BASE_DIR / "hf_cache"), 
                torch_dtype=dtype
            ).to(device)
            
            inputs = processor(
                text=[f"{req.prompt}, {req.bpm} bpm, instrumental background"],
                padding=True,
                return_tensors="pt",
            ).to(device)
            
            tokens = min(1500, int(req.duration_s * 50))
            with torch.inference_mode():
                audio_values = model.generate(**inputs, max_new_tokens=tokens)
            
            sampling_rate = model.config.audio_encoder.sampling_rate
            sf.write(str(out_wav), audio_values[0, 0].float().cpu().numpy(), sampling_rate)
            
            del model
            del processor
            free_gpu()
            
            if req.duration_s > 45.0:
                loop_wav = OUTPUT_DIR / f"music_{job_id}_loop.wav"
                subprocess.run([
                    "ffmpeg", "-y", "-v", "error", "-stream_loop", "1", "-i", str(out_wav),
                    "-t", str(req.duration_s), "-af", f"afade=t=out:st={req.duration_s - 2.5}:d=2.5",
                    str(loop_wav)
                ], check=True)
                out_wav = loop_wav
                
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
                "-c:a", "libmp3lame", "-b:a", "256k", str(out_mp3)
            ], check=True)
            
            print(f"[Music Fallback] MusicGen completado exitosamente en {time.time() - t_start:.2f}s en dispositivo: {device}")
            from fastapi.responses import FileResponse
            return FileResponse(str(out_mp3), media_type="audio/mpeg", filename=f"music_{job_id}.mp3")
        except Exception as e2:
            free_gpu()
            print(f"[Music Error] Fallo al generar con MusicGen: {e2}")
            raise HTTPException(status_code=500, detail=f"Error generando música: {e2}")

class FastTTSRequest(BaseModel):
    text: str
    voice: str = "es-MX-DaliaNeural"
    rate: str = "+0%"

@app.post("/tts/fast")
async def tts_fast(req: FastTTSRequest):
    import edge_tts
    job_id = uuid.uuid4().hex[:10]
    out_wav = OUTPUT_DIR / f"vo_{job_id}.wav"
    out_mp3 = OUTPUT_DIR / f"vo_{job_id}.mp3"
    
    # Soporte nativo de WordBoundary de Edge-TTS: fidelidad ortográfica 100% y cero alucinaciones ASR
    communicate = edge_tts.Communicate(req.text, req.voice, rate=req.rate, boundary="WordBoundary")
    words = []
    with open(str(out_mp3), "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = round(chunk["offset"] / 10_000_000, 3)
                d = round(chunk["duration"] / 10_000_000, 3)
                words.append({"w": chunk["text"], "s": s, "e": round(s + d, 3)})
                
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_mp3), "-ar", "44100", "-ac", "1", str(out_wav)], check=True)
    
    # Fallback matemático en caso de que el stream no retorne eventos (cero Whisper)
    if not words:
        all_words = req.text.split()
        d_raw = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out_wav)], capture_output=True, text=True).stdout.strip()
        tot_d = float(d_raw) if d_raw else 5.0
        tot_chars = sum(len(w) for w in all_words) or 1
        cur_t = 0.0
        for w in all_words:
            w_dur = round(tot_d * (len(w) / tot_chars), 3)
            words.append({"w": w, "s": round(cur_t, 3), "e": round(cur_t + w_dur, 3)})
            cur_t += w_dur
    dur = words[-1]["e"] if words else 0.0
    return {
        "status": "success",
        "audio_url": f"/output/vo_{job_id}.wav",
        "duration_s": dur,
        "words": words
    }

class KokoroRequest(BaseModel):
    text: str
    voice: str = "em_alex"
    speed: float = 1.0
    lang: str = "e"

@app.post("/tts/kokoro")
def tts_kokoro(req: KokoroRequest):
    import numpy as np
    from kokoro import KPipeline
    job_id = uuid.uuid4().hex[:10]
    out_wav = OUTPUT_DIR / f"kokoro_{job_id}.wav"
    
    print(f"[Kokoro] Generando voz ({req.voice}, lang={req.lang}) para: '{req.text[:40]}...'")
    try:
        pipeline = KPipeline(lang_code=req.lang)
        generator = pipeline(req.text, voice=req.voice, speed=req.speed)
        all_audio = []
        for result in generator:
            if result.audio is not None:
                all_audio.append(result.audio.cpu().numpy())
        if not all_audio:
            raise HTTPException(status_code=500, detail="Kokoro no produjo audio")
            
        full_audio = np.concatenate(all_audio)
        sf.write(str(out_wav), full_audio, 24000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Kokoro: {e}")
        
    d_raw = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out_wav)], capture_output=True, text=True).stdout.strip()
    tot_d = float(d_raw) if d_raw else len(full_audio)/24000.0
    
    # Mapeo exacto de palabras originales (cero errores ortográficos)
    all_words = req.text.split()
    tot_chars = sum(len(w) for w in all_words) or 1
    words = []
    cur_t = 0.0
    for w in all_words:
        w_dur = round(tot_d * (len(w) / tot_chars), 3)
        words.append({"w": w, "s": round(cur_t, 3), "e": round(cur_t + w_dur, 3)})
        cur_t += w_dur
        
    return {
        "status": "success",
        "audio_url": f"/output/kokoro_{job_id}.wav",
        "duration_s": tot_d,
        "words": words
    }

@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(...),
    language: str = Form("es"),
    ref_file: UploadFile = File(...)
):
    job_id = uuid.uuid4().hex[:10]
    ref_path = TEMP_DIR / f"ref_{job_id}_{ref_file.filename}"
    out_wav = OUTPUT_DIR / f"clone_{job_id}.wav"
    
    with open(ref_path, "wb") as f:
        content = await ref_file.read()
        f.write(content)
        
    print(f"[XTTS] Clonando voz para: '{text[:40]}...' | Ref: {ref_path.name}")
    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
        tts.tts_to_file(
            text=text,
            speaker_wav=str(ref_path),
            language=language,
            file_path=str(out_wav)
        )
        del tts
        free_gpu()
    except Exception as e:
        free_gpu()
        raise HTTPException(status_code=500, detail=f"Error en XTTS-v2: {e}")
        
    words = []
    try:
        from faster_whisper import WhisperModel
        whisper = WhisperModel("base", device="cuda", compute_type="float16")
        segments, _ = whisper.transcribe(str(out_wav), language=language, word_timestamps=True)
        for s in segments:
            for w in s.words:
                words.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
        del whisper
        free_gpu()
    except Exception as ew:
        print(f"[Whisper Warning] Fallback en alineación: {ew}")
        free_gpu()
        
    dur = words[-1]["e"] if words else 0.0
    return {
        "status": "success",
        "audio_url": f"/output/clone_{job_id}.wav",
        "duration_s": dur,
        "words": words
    }

@app.post("/align")
async def align_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("es")
):
    job_id = uuid.uuid4().hex[:10]
    temp_path = TEMP_DIR / f"align_{job_id}_{audio_file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await audio_file.read())
        
    words = []
    try:
        from faster_whisper import WhisperModel
        whisper = WhisperModel("base", device="cuda", compute_type="float16")
        segments, _ = whisper.transcribe(str(temp_path), language=language, word_timestamps=True)
        for s in segments:
            for w in s.words:
                words.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
        del whisper
        free_gpu()
    except Exception as e:
        free_gpu()
        raise HTTPException(status_code=500, detail=f"Error en alineación Whisper: {e}")
        
    return {
        "status": "success",
        "duration_s": words[-1]["e"] if words else 0.0,
        "words": words
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
