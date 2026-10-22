# Reproducción automatizada GEO-004

La operación cotidiana no requiere acciones del supervisor. Los siguientes pasos
son para agentes y CI; el workflow `geo004-web.yml` los ejecuta en un runner
estándar gratuito de repositorio público, sin caché ni Actions Artifacts.

1. Instalar dependencias fijadas Python 3.12 / Node22 desde los archivos lock.
2. Descargar la Release inmutable `geo003-world001-3f5c050a07c6`; `prepare_web_source.py --visual --topography` verifica el SHA del ZIP y extrae únicamente miembros explícitos del baseline.
3. `GeoPipeline.geo004_sources` descarga el ZIP oficial INEGI y dos rejillas verticales abiertas fijadas por hash; valida retícula, stencil sin NoData y transformación explícita. Escribe un directorio nuevo.
4. `GeoPipeline.geo004` usa únicamente inputs urbanos originales y el nuevo MDT; nunca sobrescribe salidas anteriores. Exporta sistemas/celdas, semántica, portales y procedencia.
5. Ejecutar pytest, pruebas Node, `geo004_audit` antes/después y `geo004_validation`. `check_geo004_acceptance.py` exige conservación espacial y ausencia de regresiones geométricas especificadas; no certifica cotas absolutas.
6. `build_geo004_web.py` empaqueta ambos modelos, fondo regional y visuales WORLD-002 independientes. El DEM Copernicus regional previo también se verifica por SHA. `validate_web_viewer.py` contrasta todas las mallas de los sectores con el GLB nuevo.
7. Pruebas Chromium reales: tres pares de cámaras, cambios de modelo, zonas renderizadas fuera del panel, consulta por raycast, mapas de calor, memoria residente, calidad alta y noche. Software SwiftShader: el rendimiento no representa una GPU comercial.
8. `prepare_geo004_evidence.py` copia diez PNG originales seleccionados y recibos; el sitio combinado debe medir menos de 50 MiB. El publicador conserva el historial de `gh-pages` y sólo reemplaza los archivos que su manifest declara generados.
9. La publicación usa URL CDN de commit inmutable porque la integración no dispone de los permisos Pages/Administration necesarios para activar GitHub Pages. No se modifica la restricción del propietario sobre PR desde Actions; el PR se abre mediante acceso directo autorizado.

El cambio de fuente es reversible: TIFF NAVD88, transformación vertical,
Copernicus remuestreado, delta fuente y referencias SHA originales. Las bases de
edificios quedan registradas por ID en CSV; los perfiles viales incluyen cotas
exportadas reales, valores ausentes explícitos y marcas de estimación estructural.
No se aplican offsets de mediana ni suavizado para aparentar precisión.

La recuperación `geo004-release.yml` restaura el despliegue por commit, comprueba
que su código corresponde al commit validado y ejecuta el navegador contra la URL
pública. Reconstruye los outputs perdidos del runner y exige un GLB de SHA idéntico
al aprobado antes de empaquetar. Consulta las variables oficiales de límites en
el repositorio `github/docs` mediante API, registra sus blobs y verifica cada
asset descargado tras publicar. No repite una validación geométrica distinta ni
reemplaza el modelo para disimular un fallo del empaquetador.
