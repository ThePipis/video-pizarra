# Lecciones aprendidas (léelo cuando algo se vea raro)

## Lo que el público/cliente rechazó
- **Historia sin texto que explique** → "no se entiende". El texto explica cada punto; los gags acompañan.
- **Hook lento** (el personaje despierta, contexto primero) → "se tarda mucho". Primera frase en ~0.2 s.
- **Todas las transiciones iguales** (paneo de cámara repetido) → aburrido. Cada una distinta y motivada.
- **Transiciones largas** (>1 s) o esperas antes de ellas → se siente lento. 0.4–0.8 s.
- **El mismo lápiz/plumón en todas las escenas** → monótono. Alterna herramientas y escenas sin herramienta.
- **Mismo fondo en todo** → plano. Cada escena su fondo.
- **Logo de marca en el personaje** sin que lo pidan → quitarlo. Ropa lisa por defecto.
- **Cifras deducidas** (p. ej. "precio anterior $5/$25" calculado desde un −20%) → no inventar; solo datos de la fuente.

## Bugs técnicos y su solución
| Síntoma | Causa | Solución |
|---|---|---|
| Todas las escenas en negro/invisibles | `tl.fromTo` aplicó sus valores FROM (opacity 0, fuera de cuadro) al construir | `immediateRender: false` en ese tween |
| Elemento corrido de lugar tras escalar/rotar | GSAP `svgOrigin`/`transformOrigin` dentro de grupos rotados o con transforms previos | usar `mover()` o un proxy + `onFrame` que escriba el `transform` directo; para sellos `stamp()` |
| Escena que queda aplastada/delgada al saltar a un tiempo posterior | un updater solo escribe durante la transición y deja el último valor | escribir el estado final también después (`else if (T >= end) …`) |
| Paneles faltantes o corridos en el mosaico final | restos de transiciones (escala 60, y −1920, clip) | el finale ya resetea `inner`; agrega `resets` para props sueltos |
| Texto cortado al revelarse | el clip del texto se mide antes de cargar la fuente | el motor espera a `document.fonts`; si agregas fuentes, añádelas a `fontLoads` |
| Personaje tapa el texto | tamaños: la mascota mide ~171×escala de alto (+ sombra) | calcula `y` de pies y deja 60–80 px al texto |
| Archivo de 150–200 MB | la línea "viva" y el grano cambian cada cuadro | usa la copia `-movil.mp4` (2 pasadas a 2.6 Mbps) para compartir |
| Audio bajo en redes | mezcla sin normalizar | `build.sh` ya aplica `loudnorm` a −14 LUFS |
| Subtítulos con errores ortográficos / alucinaciones ("Condaque", "Chad Jepetes", "explote") | Backend usaba Faster-Whisper ASR sobre audio sintético | NUNCA usar ASR sobre texto ya conocido; usar `boundary="WordBoundary"` nativo de Edge-TTS en el servidor `/tts/fast` para 100% fidelidad ortográfica |
| Desincronización de audio y pausas mudas con video corriendo | FFmpeg `apad=pad_dur=X` añade X segundos de silencio puro tras cada clip en vez de rellenar | Usar `adelay` con `amix` y calcular duración de escena dinámicamente: `sc['dur'] = dur_voz + lead_in + lead_out` (0.35s / 0.35s) |

## QA que sí atrapa errores
- Hoja de contacto cada 1.2 s de todo el video.
- Capturas cada 0.2 s alrededor de cada transición (usa `hits.json` para saber dónde caen).
- Revisa el primer cuadro (¿aparece algo en <0.5 s?) y el último (¿se lee el CTA?).
