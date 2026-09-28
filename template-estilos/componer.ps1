# La persona se grabó a cámara: su video (A-roll, ya limpio) es la base y la animación va ENCIMA solo en los tramos
# animados (RANGES de timing.js). Fuera de esos tramos se ve su cara. Voz de la grabación normalizada a -14 LUFS.
# Uso: .\componer.ps1 -ARoll <aroll.mov|mp4> [-Name nombre]     -> nombre.mp4 + nombre-movil.mp4 (< 25 MB)
param (
    [Parameter(Mandatory=$true)]
    [string]$ARoll,
    [string]$Name = "video-final"
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path $ARoll)) {
    Write-Error "No se encontró el archivo A-Roll: $ARoll"
}

Write-Host ">>> [1/4] Evaluando rangos de animación en timing.js..." -ForegroundColor Cyan
$EN = node -e "import('./timing.js').then(m=>{const r=m.RANGES||[];console.log(r.length?r.map(([a,b])=>'between(t,'+a+','+b+')').join('+'):'1')})"

Write-Host ">>> [2/4] Renderizando capa animada..." -ForegroundColor Cyan
node render.mjs _anim.mp4

Write-Host ">>> [3/4] Componiendo A-Roll y B-Roll animado con FFmpeg..." -ForegroundColor Cyan
ffmpeg -y -v error -i "$ARoll" -i _anim.mp4 -filter_complex `
  "[1:v]scale=iw:ih,setpts=PTS-STARTPTS[an];[0:v][an]overlay=0:0:enable='$EN'[v];[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]" `
  -map "[v]" -map "[a]" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 44100 -shortest -movflags +faststart "$Name.mp4"

$D = (ffprobe -v error -show_entries format=duration -of csv=p=0 "$Name.mp4").Trim()
$dur = [double]$D
$calcBr = [int][Math]::Max(1200, [Math]::Min(6000, [int](25 * 8 * 1000 / $dur - 160)))

Write-Host ">>> [4/4] Generando copia optimizada para móvil..." -ForegroundColor Cyan
$sizeBytes = (Get-Item "$Name.mp4").Length
if ($sizeBytes -le 26214400) {
    Copy-Item "$Name.mp4" "$Name-movil.mp4"
} else {
    $nullDevice = if ($IsWindows -or $env:OS -match "Windows") { "NUL" } else { "/dev/null" }
    ffmpeg -y -v error -i "$Name.mp4" -c:v libx264 -preset fast -b:v "${calcBr}k" -c:a aac -b:a 128k -movflags +faststart "$Name-movil.mp4"
}

Remove-Item -Force -ErrorAction SilentlyContinue ffmpeg2pass*, _anim.mp4

$size1 = "{0:N2} MB" -f ((Get-Item "$Name.mp4").Length / 1MB)
$size2 = "{0:N2} MB" -f ((Get-Item "$Name-movil.mp4").Length / 1MB)
Write-Host "=========================================" -ForegroundColor Green
Write-Host "LISTO:" -ForegroundColor Green
Write-Host "  Master:  $Name.mp4 ($size1)" -ForegroundColor Green
Write-Host "  Móvil:   $Name-movil.mp4 ($size2)" -ForegroundColor Green
Write-Host "  Duración: ${D}s" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
