#!/usr/bin/env bash
# Full render: video → audio mix (music + synthesized SFX) → loudness → phone copy (<30 MB).
# Usage: ./build.sh <name>      e.g. ./build.sh mi-video
set -e
NAME=${1:-video}
MUSIC=audio/music.mp3; [ -f "$MUSIC" ] || MUSIC=""
node render.mjs "_$NAME-silent.mp4" --mode A
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "_$NAME-silent.mp4")
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python; [ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
SWELL=1 $PY sfx_mix.py "$D" "audio/_$NAME-mix.wav" $MUSIC
ffmpeg -y -v error -i "_$NAME-silent.mp4" -i "audio/_$NAME-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$NAME.mp4"
# phone/share copy (<30 MB)
SIZE=$(stat -c%s "$NAME.mp4" 2>/dev/null || stat -f%z "$NAME.mp4" 2>/dev/null || wc -c < "$NAME.mp4")
if [ "$SIZE" -le 31457280 ]; then
  cp "$NAME.mp4" "$NAME-movil.mp4"
else
  ffmpeg -y -v error -i "$NAME.mp4" -c:v libx264 -preset fast -b:v 2600k -c:a aac -b:a 128k -movflags +faststart "$NAME-movil.mp4"
fi
rm -f "_$NAME-silent.mp4"
echo "LISTO: $NAME.mp4 ($(du -h "$NAME.mp4" | cut -f1)) · $NAME-movil.mp4 ($(du -h "$NAME-movil.mp4" | cut -f1)) · ${D}s"
