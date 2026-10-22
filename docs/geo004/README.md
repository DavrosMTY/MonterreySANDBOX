# GEO-004 — auditoría topográfica y reconstrucción con DTM

Trabajo en `feature/geo004-topography-audit`, desde WORLD-002 `ce1ce4b`;
depende de PR #5 y éste de PR #4. No se fusiona ningún PR. Presupuesto US$0.
Los datos GIS y entregables anteriores se conservan; UE 5.6.1 no se ejecuta.

## Hallazgos iniciales reproducidos

El DSM Copernicus es un modelo de superficie de ~30 m, EGM2008 y WGS84;
el GEO-001 lo reproyectó a EPSG:32614 y remuestreó bilinealmente cada 3,968 m.
Eso no creó mediciones de 4 m. GEO-003 ajustó perfiles con un LP y aplicó
un delta al terreno por distancia a la vía más cercana; esa selección produce
cambios entre perfiles distintos. Sus gradientes llegan a 133,37 %, frente a
46,98 % del campo inicial. Hay 996 vértices con incremento inducido de pendiente
>15 puntos, pendiente final >35 % y delta >0,5 m; se investigan por causa de
la corrección, no se consideran por sí solos un error de la topografía real.

La lectura completa de las superficies viales encontró 10.569 triángulos con
diferencia >0,25 m respecto a su propio campo de soporte y 195 piezas a nivel
con faldones verticales >1 m (máximo 7,65 m). Algunas tapas muy delgadas tienen
pendientes triangulares extremas por discontinuidad y precisión de intercambio.
Esto amplía la auditoría más allá de los 97 tramos previamente señalados.

Los túneles de GEO-003 eliminaron 17.101,6 m² sobre corredores completos;
la reconstrucción separa el terreno natural de los portales/volúmenes estimados.
No se detecta una multiplicación de unidades o una exageración vertical del visor:
los problemas se originan en DSM, perfiles procedurales y triangulación/soporte.
Las comprobaciones numéricas y de malla son distintas de la exactitud topográfica.

## Fuente adquirida

INEGI: **MDT LiDAR de 5 m G14C26A3**, producto `702825404925`, datos fuente 2007,
creación 2008, edición ASCII 2012. Su ZIP oficial público cubre el piloto completo.
Tiene NAVD88 vertical e ITRF92 época 1988.0 / UTM14N horizontal (EPSG:4487).
El campo EPV está vacío; la retícula de 5 m y los decimales almacenados no certifican
su exactitud. Densidad de puntos de terreno declarada: 0,012/m². El catálogo
consultado cubre el piloto con LiDAR 5 m, pero no con MDT 1,5 m.

[Manifest de adquisición](../../manifests/geo004-sources.json) fija URL, SHA256,
licencia y rejillas. Los [metadatos originales](source-metadata/) se conservan.
Los términos actuales de libre uso de INEGI permiten copiar, adaptar, extraer y
usar comercialmente con crédito, metadatos y aviso de transformación independiente.
La referencia antigua a centros de venta en el HTML de 2008 no es una contratación:
la descarga actual es pública y gratuita en el catálogo oficial.

El pipeline conserva EGM2008: aplica de forma explícita la operación mexicana
NAVD88/GGM10 + EGM2008 2,5' registrada en PROJ, con rejillas abiertas fijadas por hash.
No usa una rejilla estadounidense por proximidad ni un fallback ballpark. La operación
no publica una exactitud compuesta. El texto de 2008 menciona GGM05: se conserva
esa incertidumbre de realización; no se afirma invertir exactamente GGM05 ni obtener
alineación absoluta centimétrica. No se resta una mediana arbitraria como datum.

## Reconstrucción y validación

El terreno natural conserva los planos de la retícula INEGI de 5 m y sus pendientes.
No se aplica el LP de GEO-003 ni su deformación por vía más cercana. Las plataformas
a nivel se recortan contra cada triángulo nativo del MDT: así no interpolan una tapa
a través de varios planos distintos. La base delgada no se prolonga hasta una
superficie independiente, origen de los faldones artificiales anteriores.

Puentes y túneles conservan geometría independiente, componentes identificados,
perfiles de centro de vía estimados, transiciones y apoyos procedurales señalados.
Los perfiles estructurales no son mediciones del MDT. El terreno no se deforma
para satisfacerlos. Los portales usan máscaras locales explícitas, nunca una
excavación de todo el corredor. Las cimentaciones se revisan sin aplanar sus parcelas.

Cada terreno se exporta a GeoTIFF y GLB, con OBJ/MTL por sistema/celda para futura
integración UE. La cuadrícula nativa de 401 vértices **no** se presenta como un
Landscape RAW válido. El proyecto UE5.6.1 permanece sin modificar y no se ha
compilado, importado ni ejecutado Unreal. Los OBJ usan ejes Unreal y centímetros locales, con pivotes
también en centímetros (GLB/web y cálculos GIS permanecen en metros); la adaptación del importador GEO-003 al nuevo manifest y
las colisiones necesitan validación en el motor.

[Fuentes y legalidad](FUENTES.md) · [Resultados y límites](RESULTADOS.md) ·
[Reproducción](REPRODUCCION.md). Los recibos de CI y verificación pública se añaden
cuando las operaciones correspondientes terminan; su ausencia no significa éxito.

## Visor

Se conserva WORLD-002 y su URL histórica. GEO-004 contiene ambos modelos reales,
streaming de 64 sectores por modelo, controles originales de calidad/iluminación,
mapa de calor con las revisiones pendientes y consulta de cota EGM2008/pendiente.
Los tres casos auditados restablecen cámaras idénticas antes/después. El calor no
certifica la exactitud fuera de sus celdas coloreadas. La pendiente consultada es
una derivada por diferencias a escala de la retícula; no una pendiente levantada.

La captura mencionada en la solicitud no se recibió con el texto; los casos se
seleccionan por anomalías medidas de las mallas, con coordenadas geográficas.
No se utiliza contenido geográfico de Google. Las capturas publicadas son PNG
sin retoques producidos por Chromium, no imágenes generadas ni capturas Unreal.

[Visor GEO-004 desplegado](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/eff5f62d9634f7282071a8a40a46ab4b510811d6/index.html) ·
[Comparación PNG auténtica](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/eff5f62d9634f7282071a8a40a46ab4b510811d6/evidence/index.html) ·
[PR #6](https://github.com/DavrosMTY/MonterreySANDBOX/pull/6).
[Prerelease descargable](https://github.com/DavrosMTY/MonterreySANDBOX/releases/tag/geo004-aa0797108638):
modelo/terreno/QA de 39 MB y sitio estático de 36 MB, ambos descargados y
verificados por SHA256 después de publicar. [Recibo de descarga](release-verification.json)
y [prueba pública](public-verification.json) identifican los commits y workflows.

El primer job aprobó reconstrucción, QA, WebGL y despliegue, pero falló en el
empaquetador. La recuperación conserva esos resultados y publica los archivos
sin sustituir la geometría validada. El job intermedio pasó la prueba pública y
se canceló después para corregir una frase sobre unidades antes de empaquetar.
El job final `39834048694` terminó correctamente; reutilizó la prueba de la misma
URL inmutable y verificó que el GLB regenerado era idéntico. Los recibos distinguen
la validación de datos/navegador de la publicación y no ocultan los intentos fallidos.

La vista previa CDN es gratuita y sin SLA; puede mostrar un aviso externo con
publicidad antes del visor. Si aparece, **Open the page** abre la aplicación.
La aplicación sólo solicita los estáticos del proyecto. GitHub Pages no está
activado: la integración disponible no tiene Pages/Administration de escritura;
la URL alternativa ya funciona y no requiere tareas manuales del supervisor.
