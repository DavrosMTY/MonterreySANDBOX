# FREE-001 — resultados verificables

21 de octubre de 2026, America/Mexico_City. **US$0 en servicios contratados**:
no VM, prueba con tarjeta, backend de pago, LFS ni almacenamiento Actions Artifacts.
Unreal Engine no se instaló, compiló ni ejecutó.

## Datos y optimización

Fuente: GEO-003 / WORLD-001 real, GLB SHA256
`c07d1a91e37bea063c638cb51275a770ed0ab222c7a2b6c49f6a7dc30436bcfc`.
El readback exhaustivo validó todos los sectores contra ese original, incluyendo
índices, posiciones, colores y las fichas originales con IDs/procedencia.

| Métrica | Original | Web |
| --- | ---: | ---: |
| Triángulos | 1.077.198 | **1.077.198, conservados** |
| Piezas / mallas de render | 2.673 | **279** agrupadas, reducción de 89,56 % |
| GLB original / transporte de sectores | 24.161.568 bytes | **9.136.230 bytes**, reducción de 62,19 % |
| Original también gzip / sectores gzip | 9.401.366 bytes | **9.136.230 bytes**, ahorro equivalente de 2,82 % |
| Sectores de carga | Un GLB monolítico | **64** sectores de 250 m |
| Edificios / tramos OSM fuente | 1.136 / 2.665 | Conservados; sin regenerar geografía |
| Error máximo de posición del readback | — | **0,000007617 m**, unos 0,008 mm |

La reducción de mallas es de agrupación, no de edificios ni triángulos. No se
han sustituido alturas, huellas o calles por una ciudad ficticia. El 62,19 % compara GLB sin comprimir con transporte gzip, no atribuye todo el
ahorro al empaquetado. Comprimiendo también el original, el ahorro de bytes es
2,82 %. La ventaja principal para explorar es cargar sólo los sectores cercanos y
agrupar draw calls. El máximo
permitido en QA es 0,1 mm; las coordenadas UTM/datum se retienen en el manifest.

Sitio desplegado: **14.733.780 bytes** incluyendo vendor, catálogo de fichas,
licencias y evidencia. El catálogo de fichas y las capturas no se descargan en
la navegación normal. El publicador rechaza sitios mayores de 50 MiB.

## Comparación de calidad en navegador

[Build y pruebas en GitHub](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39686834229).
Chromium, viewport 1280 × 800, misma vista aérea, **ANGLE SwiftShader por software**.
Son muestras breves después de calentamiento, no un ensayo estadístico ni una
medición de GPU de consumidor. El hardware del runner y la carga del host pueden
variar. El modo bajo carga menos mundo y píxeles: no es una comparación a igual
calidad ni una demostración aislada del efecto de agrupar mallas.

| Métrica medida | Equilibrada | Baja |
| --- | ---: | ---: |
| Sectores residentes | 32 | 12 |
| Resolución interna | 1280 × 800 | 896 × 560 |
| Triángulos dibujados en la muestra | 552.192 | 246.686 |
| Draw calls en la muestra | 142 | 59 |
| Buffers de geometría estimados | 8,44 MiB | 3,59 MiB |
| FPS, build/QA local del runner | **2,78** | **7,83** |
| FPS, prueba HTTPS pública posterior | **1,98** | **3,89** |

La muestra baja resultó ~2,8 veces más rápida en el primer job y ~2 veces en la
prueba pública posterior; usó ~57,5 % menos buffers residentes. La variación entre
jobs confirma que estos FPS no son una garantía de rendimiento.
No se promete 30/60 FPS en este entorno sin GPU. La vista de calle cambia visibilidad
y draw calls; no se extrapola el FPS aéreo a todo el recorrido. El heap JS no baja
necesariamente al mismo tiempo por la recolección de basura. No se midió VRAM total.
No se midió FPS del GLB monolítico original a idéntica cámara: su comparación
anterior es de tamaño, topología y mallas potenciales, no de FPS antes/después.

## Pruebas realizadas

- **77 pruebas Python previas**, todas satisfactorias en el entorno local. La CI
  base valida además Linux/Windows; no compila Unreal.
- **4 pruebas unitarias JS**: selección en bordes de celda, liberación al cambiar
  de zona, descarte de respuestas tardías y fallo de red sin retry continuo.
- Readback de **64 GLB / 2.673 fichas / 1.077.198 triángulos**; hash y colores/IDs
  originales preservados, sin piezas ausentes/duplicadas.
- Navegador real: render GLB, dos calidades, liberación de sectores, reducción de
  memoria/resolución, WASD, rotación con mouse, presets aéreo/calle y controles
  móviles visibles. Sin errores JS. En la URL pública se permiten sólo el CDN y
  la redirección de GLB gzip al mismo repositorio/SHA en GitHub; no hay backend
  ni consultas a mapas/servicios de pago.
- Política de publicación: inputs licenciados intactos y dependencias, modelos,
  cachés, ZIP y renders fuera de la rama de código. Los pequeños assets estáticos
  se publican únicamente en la rama de hosting autorizada.

[Recibo geométrico](geometry-validation.json). El sitio conserva los recibos
completos y las capturas PNG auténticas en `evidence/`, fijados al SHA del hosting.
Las capturas son de Chromium; no son renders de Unreal ni imágenes generadas por IA.

## Publicación y bloqueo separado

Rama de implementación: `feature/free001-web-viewer`, desde development.
Rama de hosting generada: `gh-pages`, sin force push ni sustitución de trabajo ajeno.
Despliegue verificable: `dd44f8e0a6eccf8be3362685a2ab847758fb38bb`.

GitHub negó la creación de Pages con HTTP 403 tanto por la integración directa
como por GITHUB_TOKEN con pages:write. Por eso el éxito del job de build **no**
se presenta como un sitio Pages activo. El resultado exacto está en
`gh-pages/evidence/pages.json`. La **[vista pública gratuita por CDN](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/dd44f8e0a6eccf8be3362685a2ab847758fb38bb/index.html)** pasó su prueba independiente:
[workflow](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39688508184) y
[recibo](public-verification.json). En el primer acceso, el proveedor muestra un
aviso externo con publicidad y el botón «Open the page»; el test sigue ese flujo
normal, sin introducir credenciales. La aplicación servida después no contiene
anuncios ni servicios de pago. El proveedor no ofrece SLA y no sustituye Pages.
Se registraron 35 redirecciones estáticas de GLB al mismo SHA en GitHub y cero
peticiones a servicios no autorizados durante la aplicación.

Unreal sigue intacto y UE-001 permanece en PR #2 sin fusionar. C/D/E continúan
bloqueados por ausencia del motor/hardware; navegar este visor no los aprueba.
El siguiente trabajo gratuito viable es inspeccionar con este visor los perfiles
viales y cruces marcados por GEO-003, conservando la geometría fuente y generando
correcciones en ramas/PR separados.
