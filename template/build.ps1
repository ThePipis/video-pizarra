# Render completo (Windows/PowerShell): video -> mezcla de audio (música + SFX procedurales) -> loudnorm -14 LUFS -> copia móvil (<30 MB).
# Uso: .\build.ps1 [nombre]       Ej: .\build.ps1 mi-video
param (
    [string]$Name = "video",
    [switch]$SoloMovil,
    [switch]$SoloMaster,
    [switch]$DualEncode,
    [switch]$Draft
)
$ErrorActionPreference = "Stop"

$Music = "audio/music.mp3"
if (-not (Test-Path $Music)) { $Music = "" }

$Workers = 6
$DraftArg = if ($Draft) { "--draft" } else { "" }

if ($Draft) {
    Write-Host ">>> [1/4] Renderizando en MODO BORRADOR ULTRA-RÁPIDO (720p @ 24 FPS, $Workers workers)..." -ForegroundColor Yellow
} else {
    Write-Host ">>> [1/4] Renderizando en MODO PRODUCCIÓN (1080p @ 30 FPS, $Workers workers)..." -ForegroundColor Cyan
}

if ($Draft) {
    node render.mjs "_$Name-silent.mp4" --mode A --workers $Workers --draft
} else {
    node render.mjs "_$Name-silent.mp4" --mode A --workers $Workers
}

$D = (ffprobe -v error -show_entries format=duration -of csv=p=0 "_$Name-silent.mp4").Trim()

$Py = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } elseif (Test-Path ".venv/bin/python") { ".venv/bin/python" } else { "python" }

Write-Host ">>> [2/4] Sintetizando efectos de sonido y mezclando audio ($Py)..." -ForegroundColor Cyan
$env:SWELL = "1"
if ($Music) {
    & $Py sfx_mix.py $D "audio/_$Name-mix.wav" $Music
} else {
    & $Py sfx_mix.py $D "audio/_$Name-mix.wav"
}

$Vo = "audio/vo.wav"

if ($SoloMovil) {
    Write-Host ">>> [3/3] Masterizando directamente versión para móvil (<30 MB, -14 LUFS)..." -ForegroundColor Cyan
    if (Test-Path $Vo) {
        ffmpeg -y -v error -i "_$Name-silent.mp4" -i "$Vo" -i "audio/_$Name-mix.wav" `
          -filter_complex "[1:a]volume=1.1[v];[2:a]volume=0.32[bg];[v][bg]amix=inputs=2:duration=first:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]" `
          -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart "$Name-movil.mp4"
    } else {
        ffmpeg -y -v error -i "_$Name-silent.mp4" -i "audio/_$Name-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 `
          -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart "$Name-movil.mp4"
    }
    Remove-Item -Force -ErrorAction SilentlyContinue "_$Name-silent.mp4"
    $fileBytes = (Get-Item "$Name-movil.mp4").Length
    if ($fileBytes -gt 30MB) {
        Write-Host ">>> [Aviso] Archivo >30MB, aplicando compresión secundaria..." -ForegroundColor Yellow
        ffmpeg -y -v error -i "$Name-movil.mp4" -c:v libx264 -preset fast -b:v 2600k -maxrate 3200k -bufsize 6000k -c:a copy -movflags +faststart "$Name-movil-tmp.mp4"
        Move-Item -Force "$Name-movil-tmp.mp4" "$Name-movil.mp4"
    }
    $size2 = "{0:N2} MB" -f ((Get-Item "$Name-movil.mp4").Length / 1MB)
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "LISTO (Solo Móvil):" -ForegroundColor Green
    Write-Host "  Móvil:   $Name-movil.mp4 ($size2)" -ForegroundColor Green
    Write-Host "  Duración: ${D}s" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
    exit 0
}

if (Test-Path $Vo) {
    Write-Host ">>> [3/4] Masterizando video final con Voz (Locutor) + Música + SFX a -14 LUFS..." -ForegroundColor Cyan
    ffmpeg -y -v error -i "_$Name-silent.mp4" -i "$Vo" -i "audio/_$Name-mix.wav" `
      -filter_complex "[1:a]volume=1.1[v];[2:a]volume=0.32[bg];[v][bg]amix=inputs=2:duration=first:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]" `
      -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$Name.mp4"
} else {
    Write-Host ">>> [3/4] Masterizando video final a -14 LUFS..." -ForegroundColor Cyan
    ffmpeg -y -v error -i "_$Name-silent.mp4" -i "audio/_$Name-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 `
      -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$Name.mp4"
}

Remove-Item -Force -ErrorAction SilentlyContinue "_$Name-silent.mp4"
$size1 = "{0:N2} MB" -f ((Get-Item "$Name.mp4").Length / 1MB)
$sizeBytes = (Get-Item "$Name.mp4").Length

if ($SoloMaster) {
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "LISTO (Solo Master):" -ForegroundColor Green
    Write-Host "  Master:  $Name.mp4 ($size1)" -ForegroundColor Green
    Write-Host "  Duración: ${D}s" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
    exit 0
}

if (-not $DualEncode -and $sizeBytes -le 30MB) {
    Write-Host ">>> [4/4] Master es <= 30MB ($size1). Generando copia móvil instantánea..." -ForegroundColor Cyan
    Copy-Item "$Name.mp4" "$Name-movil.mp4"
    $size2 = $size1
} else {
    Write-Host ">>> [4/4] Generando copia optimizada para redes/móvil (<30 MB)..." -ForegroundColor Cyan
    ffmpeg -y -v error -i "$Name.mp4" -c:v libx264 -preset fast -b:v 2600k -maxrate 3200k -bufsize 6000k -c:a aac -b:a 128k -movflags +faststart "$Name-movil.mp4"
    $size2 = "{0:N2} MB" -f ((Get-Item "$Name-movil.mp4").Length / 1MB)
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host "LISTO:" -ForegroundColor Green
Write-Host "  Master:  $Name.mp4 ($size1)" -ForegroundColor Green
Write-Host "  Móvil:   $Name-movil.mp4 ($size2)" -ForegroundColor Green
Write-Host "  Duración: ${D}s" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
