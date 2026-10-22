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

## Implementación en validación

`GeoPipeline.geo004_sources` reconstruye el mosaico 5 m, rechaza NoData en el piloto,
registra la operación vertical, conserva el ZIP y exporta deltas reversibles.
`geo004_audit` mide todas las tapas y faldones a nivel y genera puntos GeoJSON,
mapa de calor y métricas del campo de soporte. `geo004` genera terreno natural sin
LP ni deformación por vías cercanas, plataformas sobre ese mismo campo, perfiles
estructurales separados y portales locales estimados. Reutiliza huellas, IDs,
alturas relativas y grafo OSM; las estructuras siguen pendientes de control vertical.

La reconstrucción, QA de intersecciones/edificios y actualización del visor están
pendientes de terminar. No se presenta un prototipo nuevo como validado por este
primer diagnóstico. La captura mencionada por el usuario no llegó con el texto;
se usan casos localizados por las métricas mientras tanto.

No se solicita ni utiliza contenido geográfico de Google. Se investigan únicamente
sus documentos legales; la geometría distribuible usa fuentes INEGI/OSM/Copernicus
con sus avisos, o elaboración independiente.
