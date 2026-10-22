# WORLD-002 — resultados y diagnóstico

## Auditoría y preservación

FREE-001 seguía en PR #4 abierto; los PR #1–#3 también estaban abiertos. Se creó
`feature/world002-visual-identity` desde su head `fab3b60e55d4f17c03e15f7acfe05744c9ca2c12`,
sin fusionarlos, reescribir historia o modificar el proyecto Unreal/inputs GIS.
Antes de WORLD-002 el visor sólo usaba materiales grises por color de vértice,
streaming de 64 celdas y tres perfiles; no tenía fachadas, mobiliario ni fondo DEM.
Las categorías y alturas desconocidas se conservaron en los registros originales.

## Validación local

- 88 pruebas Python y 5 pruebas Node aprobadas.
- Lectura completa de 64 GLB: 2.673 partes y 1.077.198 triángulos conservados;
  error máximo float32 `0.000007617187520736479 m` (límite 0,0001 m).
- 1.375 grupos/partes con atributos visuales comprobados contra sus registros fuente.
- 211.403 muestras de los tres LOD cotejadas con el TIFF Copernicus fijado por SHA256.
- 5.625 segmentos de línea condicionados por carriles/sentido explícitos; 610 rayas
  peatonales sobre 122 nodos OSM representados (no son 610 cruces independientes).
- 171 árboles: 43 nodos fuente y 128 propuestas decorativas sobre banqueta.
  12 controles semafóricos representados de 15 etiquetados; se omiten los que carecen
  de superficie válida. No se activa comportamiento de tráfico.
- Omitidos conservadoramente: 44 pinturas sobre superficie faltante/pendiente alta,
  9 objetos OSM sin suelo y 4 cruces demasiado alejados de una calzada exportada.
- Chromium/WebGL2 real: controles, carga/descarga, modo original/ciudad, día/atardecer/
  noche, sombras, mobiliario desactivable, 64 sectores en alta, LOD y ciclos de evicción.
  Cero errores de página, consola, shaders y respuestas HTTP en la ejecución local.

Los recibos finales y las capturas se publican con el sitio en `evidence/` y el
workflow conserva el informe compacto en `ci-verification.json`. La comprobación de
la URL pública se registra separadamente en `public-verification.json` al completarse.
Los informes especifican commit, renderer, cámara, sectores, buffers y checks.

## Rendimiento: alcance de la evidencia

La máquina disponible no ofrece GPU de consumo: Chromium usa ANGLE SwiftShader
por software. Las muestras FPS del HUD son ventanas cortas de la sesión; no son un
benchmark GPU, una garantía de fluidez ni resultados de Unreal. La prueba compara
Graybox/Ciudad sin cambiar cámara ni sectores. Alta carga los 64 sectores y puede
ser muy lenta bajo software; baja reduce resolución/sectores y usa copas/DEM lejanos.

Mediciones locales finales, Chromium 1280 × 800, SwiftShader, muestras cortas:

| Escena | Sectores | FPS | Draw calls | Buffers MiB |
| --- | ---: | ---: | ---: | ---: |
| Calle Graybox, baja | 11 | 9,50 | 28 | 4,10 |
| Calle Ciudad, baja | 11 | 6,61 | 48 | 4,10 |
| Calle Ciudad, sombras activadas | 11 | 5,69 | 59 | 4,10 |
| Aérea Ciudad, baja | 12 | 3,85 | 115 | 4,19 |
| Aérea Ciudad, equilibrada | 32 | 1,70 | 251 | 10,43 |
| Aérea Ciudad, alta sin sombras | 64 | 1,96 | 366 | 24,08 |

Alta y equilibrada se midieron en momentos distintos: sus ventanas no permiten
inferir que alta sea más rápida; alta tardó más en cargar/renderizar y puede contener
una transición. No son medias estabilizadas. La prueba de sombras es independiente.
Los ciclos equilibrada→baja repitieron exactamente bytes y número de geometrías.
[Mediciones completas](local-performance.json). La región visual, excluyendo panel y
FPS, tuvo diferencia absoluta media RGB frente a Graybox de aproximadamente 46/46/49
por canal (escala 0–255); no se usa sólo un cambio de texto como evidencia visual.

Se conserva íntegro el piloto en cualquier sector cargado. La capa visual añade
pintura instanciada y mobiliario, y el fondo añade 19–320 mil triángulos aproximados
según LOD. Los shaders de fachadas aumentan costo de fragmentos respecto al Graybox.
Se puede desactivar fondo/vegetación/mobiliario/pintura y sombras sin alterar GIS.

El sitio base generado ocupa ~14,2 MB decimales antes de capturas; los sectores GLB
comprimidos suman 9.163.466 bytes frente al GLB fuente de 24.161.568 bytes. La construcción local
incluyendo evidencia ocupa 24.766.878 bytes y se verifica bajo 50 MiB antes de publicar. No se usan LFS,
Actions Artifacts, caches persistentes, backend o APIs de pago.

## Problemas pendientes y siguiente trabajo viable

La identidad es una primera propuesta procedural, todavía sin fachadas fotográficas
verificadas, edificios emblemáticos modelados ni especies botánicas confirmadas.
La iluminación es artística; los semáforos son estáticos. El fondo es un DSM
georreferenciado y sus cámaras aproximadas requieren revisión visual/cartográfica
de cumbres. Persisten limitaciones viales y colisión libre del piloto.

El siguiente paso viable gratuito es revisar referencias y licencias de hitos
concretos, enriquecer metadatos de edificios y medir el visor en GPUs reales cuando
estén disponibles. No se corrigen categorías a partir de apariencias imaginadas.
Unreal 5.6.1 queda intacto: no hay evidencia de compilación, importación ni ejecución
UE en este trabajo. Pages sigue requiriendo permisos administrativos no disponibles;
la vista previa CDN gratuita tiene aviso externo y no ofrece SLA.

## Publicación de la construcción verificada

[PR #5 hacia development](https://github.com/DavrosMTY/MonterreySANDBOX/pull/5),
dependiente de PR #4, sin merge. Implementación `b175978bcf0d657e8c4ae634f4e3bb836dc5cf37`.
La reconstrucción y el navegador WORLD-002 aprobaron en GitHub:
[workflow de publicación](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39813444403)
y [workflow del PR](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39813524537).
También aprobaron la regresión FREE-001 y las suites GIS en Linux y Windows.
[Recibo CI completo](ci-verification.json).

Hosting generado `a44d909664914f088e01b23c87acb2ef8cab3c44`, descendiente del despliegue FREE-001, sin reescribir historia.
[Visor público](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/a44d909664914f088e01b23c87acb2ef8cab3c44/index.html) ·
[Galería de capturas auténticas](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/a44d909664914f088e01b23c87acb2ef8cab3c44/evidence/index.html).
La URL original FREE-001 sigue fijada a `dd44f8e0a6eccf8be3362685a2ab847758fb38bb`.
La verificación independiente HTTPS se registra en `public-verification.json`;
la aprobación del build por sí sola no certifica esa URL ni activa Pages.

La [verificación HTTPS pública](public-verification.json) aprobó el flujo normal
del aviso gratuito y todos los checks WORLD-002, sin errores de consola/render/HTTP.
[Workflow público](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39814161898).
Hubo 161 redirecciones estáticas al mismo commit de GitHub durante la exploración
completa, ninguna a servicios no autorizados dentro de la aplicación. El aviso del
proveedor tiene publicidad y se prueba por separado de la aplicación.

Se publicó un ZIP del commit exacto de hosting mediante un runner público estándar:
la integración directa devolvió HTTP 401 en uploads.github.com, aunque Git/API/PR
funcionan. El workflow usa su token efímero de contents:write, sin credenciales
compartidas ni permisos de administración. Se comprobaron límites oficiales de
Releases en GitHub Docs y sus variables fuente: 1.000 assets, cada uno <2 GiB,
sin límite total/de transferencia para Releases. [Recibo](../../manifests/world002-release-limits.json).

[Prerelease WORLD-002](https://github.com/DavrosMTY/MonterreySANDBOX/releases/tag/world002-b175978bcf0d)
con ZIP de 21.039.996 bytes, manifest, SHA256 y revisión de límites. El workflow
[descargó los cuatro assets y verificó sus hashes](release-verification.json).
El SHA256 del ZIP es `53ab49e15d33946da65137669026174c18279af3a0c6ba02d3ca534f7d14fc71`.
Son recursos del visor, no un ejecutable Unreal/Windows.

[Verificación de publicación GitHub](github-verification.json): todos los blobs
del snapshot fuente coinciden con GitHub; los heads previos permanecen intactos,
GIS/Unreal no cambiaron y PR #1–#5 permanecen abiertos sin merge. Las comprobaciones
se fijan al commit indicado; commits posteriores de documentación no alteran el
build del visor, fijado a `b175978`/hosting `a44d909`.
