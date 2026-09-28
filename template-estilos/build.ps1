# Render final (Windows/PowerShell): video -> mezcla (SFX del estilo + música + voz) -> loudness -14 LUFS -> copia para celular (<30 MB).
# Uso: .\build.ps1 [nombre]       (usa audio/music.mp3 y audio/vo.* si existen)
param (
    [string]$Name = "video",
    [switch]$SoloMovil,
    [switch]$SoloMaster,
    [switch]$DualEncode
)
$ErrorActionPreference = "Stop"

$Py = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } elseif (Test-Path ".venv/bin/python") { ".venv/bin/python" } else { "python" }

Write-Host ">>> [1/4] Renderizando fotogramas con Playwright + FFmpeg..." -ForegroundColor Cyan
node render.mjs "_$Name-silent.mp4"

$pyArgs = @("sfx_mix.py", "audio/_$Name-mix.wav")
if (Test-Path "audio/music.mp3") {
    $pyArgs += @("--music", "audio/music.mp3")
}
$voFiles = Get-ChildItem -Path "audio/vo.*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($voFiles) {
    $pyArgs += @("--vo", $voFiles.FullName)
}

Write-Host ">>> [2/4] Sintetizando efectos de sonido y mezclando audio ($Py)..." -ForegroundColor Cyan
& $Py @pyArgs

$D = (ffprobe -v error -show_entries format=duration -of csv=p=0 "_$Name-silent.mp4").Trim()
$dur = [double]$D
$calcBr = [int][Math]::Max(1200, [Math]::Min(6000, [int](25 * 8 * 1000 / $dur - 160)))
$maxRate = "$([int]($calcBr * 1.3))k"
$bufSize = "$([int]($calcBr * 2.0))k"

if ($SoloMovil) {
    Write-Host ">>> [3/3] Masterizando directamente versión para móvil (<30 MB, -14 LUFS)..." -ForegroundColor Cyan
    ffmpeg -y -v error -i "_$Name-silent.mp4" -i "audio/_$Name-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 `
      -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart "$Name-movil.mp4"
    Remove-Item -Force -ErrorAction SilentlyContinue "_$Name-silent.mp4"
    $fileBytes = (Get-Item "$Name-movil.mp4").Length
    if ($fileBytes -gt 30MB) {
        Write-Host ">>> [Aviso] Archivo >30MB, aplicando compresión secundaria..." -ForegroundColor Yellow
        ffmpeg -y -v error -i "$Name-movil.mp4" -c:v libx264 -preset fast -b:v "${calcBr}k" -maxrate $maxRate -bufsize $bufSize -c:a copy -movflags +faststart "$Name-movil-tmp.mp4"
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

Write-Host ">>> [3/4] Masterizando video final a -14 LUFS..." -ForegroundColor Cyan
ffmpeg -y -v error -i "_$Name-silent.mp4" -i "audio/_$Name-mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 44100 `
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$Name.mp4"

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
    Write-Host ">>> [4/4] Generando copia optimizada para móvil (<30 MB, bitrate ${calcBr}k)..." -ForegroundColor Cyan
    ffmpeg -y -v error -i "$Name.mp4" -c:v libx264 -preset fast -b:v "${calcBr}k" -maxrate $maxRate -bufsize $bufSize -c:a aac -b:a 128k -movflags +faststart "$Name-movil.mp4"
    $size2 = "{0:N2} MB" -f ((Get-Item "$Name-movil.mp4").Length / 1MB)
}

Write-Host "=========================================" -ForegroundColor Green
Write-Host "LISTO:" -ForegroundColor Green
Write-Host "  Master:  $Name.mp4 ($size1)" -ForegroundColor Green
Write-Host "  Móvil:   $Name-movil.mp4 ($size2)" -ForegroundColor Green
Write-Host "  Duración: ${D}s" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
