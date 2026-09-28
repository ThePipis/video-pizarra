#!/usr/bin/env bash
# Render final: video → mezcla (SFX del estilo + música + voz) → loudness -14 LUFS → copia para celular (<30 MB).
# Uso: ./build.sh <nombre>        (usa audio/music.mp3 y audio/vo.* si existen)
set -e
NAME=${1:-video}
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python; [ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
node render.mjs "_$NAME-silent.mp4"
ARGS=""; [ -f audio/music.mp3 ] && ARGS="$ARGS --music audio/music.mp3"
VO=$(ls audio/vo.* 2>/dev/null | head -1 || true); [ -n "$VO" ] && ARGS="$ARGS --vo $VO"
$PY sfx_mix.py "audio/_$NAME-mix.wav" $ARGS
ffmpeg -y -v error -i "_$NAME-silent.mp4" -i "audio/_$NAME-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$NAME.mp4"
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NAME.mp4")
# copia para celular (<30 MB)
SIZE=$(stat -c%s "$NAME.mp4" 2>/dev/null || stat -f%z "$NAME.mp4" 2>/dev/null || wc -c < "$NAME.mp4")
if [ "$SIZE" -le 31457280 ]; then
  cp "$NAME.mp4" "$NAME-movil.mp4"
else
  BR=$($PY -c "print(max(1200, min(6000, int(25*8*1000/float($D) - 160))))")
  ffmpeg -y -v error -i "$NAME.mp4" -c:v libx264 -preset fast -b:v ${BR}k -c:a aac -b:a 128k -movflags +faststart "$NAME-movil.mp4"
fi
rm -f "_$NAME-silent.mp4"
echo "LISTO: $NAME.mp4 ($(du -h "$NAME.mp4" | cut -f1)) · $NAME-movil.mp4 ($(du -h "$NAME-movil.mp4" | cut -f1)) · ${D}s"
