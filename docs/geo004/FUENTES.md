# Fuentes y límites de exactitud

Consultas del 22 de octubre de 2026. El piloto está centrado en 25,667° N,
100,310° O, 2 × 2 km. Resolución de retícula, densidad de puntos y precisión son
magnitudes diferentes. Ninguna fuente nueva certifica las elevaciones actuales
sobre puentes, túneles o cimentaciones.

| Fuente oficial | Cobertura y descarga | Resolución / precisión | Datum y fecha | Uso y decisión |
| --- | --- | --- | --- | --- |
| [INEGI MDT LiDAR](https://www.inegi.org.mx/app/geo2/elevacionesmex/), G14C26A3, UPC 702825404925 | ZIP público automatizado; cubre el 100 % del piloto; SHA fijado en manifest | Producto 5 m, terreno derivado; densidad de terreno declarada 0,012/m²; EPV vacía. Resolución vertical declarada 1 m no es exactitud | ITRF92 época 1988.0 / UTM14N, EPSG:4487; NAVD88; LiDAR 2007, creado 2008, edición ASCII 2012 | Descargado y utilizado. [Términos INEGI](https://www.inegi.org.mx/inegi/terminos.html): reutilización y adaptación comercial con crédito, metadatos y aviso de cambios |
| INEGI MDT/MDS 1,5 m | Mallas oficiales `malla10k_T1_5_min.geojson` y `malla10k_S1_5_min.geojson`: intersección 0 con el piloto consultado | 1,5 m nominal donde existe; precisión, datum y año de otro producto no se extrapolan | No hay producto del piloto adquirido | No se inventa detalle ni se presenta interpolación a 1,5 m como medición |
| [CEM 4.0 INEGI](https://www.inegi.org.mx/app/geo2/elevacionesmex/) | API `api/versiones`, `api/resoluciones?version=2`, `api/archivo?version=2&opcion=15&clave=19`; devuelve ZIP estatal `e19_cem_r15_v4_tif.zip`, ~214 MB | Catálogo actual 15 m; no se validó EPV específica del archivo | Datum y épocas de las fuentes deben verificarse en el ZIP antes de combinar | Descarga pública identificada; no se baja el estado entero porque ya existe MDT 5 m para el piloto; no se mezcla sin metadata |
| [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) | DSM previo; cubre piloto y fondo regional; TIFF original conservado con SHA | ~30 m nativos; remuestreo a 3,968 m no crea información nueva. Es superficie con edificios/vegetación | WGS84 y EGM2008; adquisición principal TanDEM-X 2011–2015 según documentación del producto; no fecha única medida del piloto | Licencia Copernicus DEM y aviso Airbus/UE previos conservados. Se mantiene como comparación y fondo distante, no terreno urbano nuevo |
| Cartografía estatal / municipal y red geodésica INEGI | Portales oficiales consultados; algunas rutas antiguas devolvieron 404 o respuesta proxy 403. [RGNA](https://www.inegi.org.mx/app/geo2/rgna/) sí responde y ofrece archivos RINEX, que no sustituyen cotas verticales de control del piloto. No se adquirió un inventario con cotas/datum/licencia verificables del piloto | No validada | No validada | Pendiente localizar puntos acotados, curvas o controles actuales autorizados. Un 404 no demuestra que los datos no existan |
| OpenStreetMap | Huellas, ejes e identificadores originales del proyecto; sin modificaciones al grafo | Planimetría colaborativa; alturas/anchos desconocidos son estimaciones | WGS84 fuente → EPSG:32614; no cotas estructurales levantadas | ODbL 1.0, atribución visible y datos derivados redistribuidos con sus avisos |

Las mallas de cobertura se obtuvieron del propio portal, no de un buscador por
nombre. [Evidencia de cobertura](coverage-access.json) y [portales adicionales consultados](additional-official-portals.json) registra URLs y hashes.
El catálogo diferencia terreno `T` y superficie `S`; se elige MDT `T`.
Los [metadatos originales](source-metadata/) conservan bytes y codificación de origen.

## Conversión vertical explícita

NAVD88 se convierte al EGM2008 del proyecto mediante la operación mexicana PROJ
con `mx_inegi_ggm10.tif` (INEGI CC BY 4.0) y `us_nga_egm08_25.tif` (NGA dominio
público). Descargas de OSGeo/PROJ-data fijadas a commit y SHA. No se emplea una
rejilla geoidal estadounidense ni fallback ballpark. La operación compuesta tiene
exactitud desconocida. El origen menciona GGM05 y el registro utiliza GGM10: se
mantiene explícita esa incertidumbre, sin declarar una inversión exacta de GGM05.
El ajuste calculado es de aproximadamente −0,152 a −0,126 m, no un offset inventado.
La ida/vuelta numérica comprueba implementación, **no precisión topográfica**.
La transformación horizontal estática tampoco certifica corrección de época.

## Google Earth / Maps

Se consultaron únicamente documentos legales oficiales; no se solicitó contenido
geográfico, imágenes, elevaciones ni 3D Tiles de Google.

- [Geo Guidelines](https://about.google/brand-resource-center/products-and-services/geo-guidelines/): prohíben usar Earth/Pro/Studio para reconstruir modelos 3D o contenido similar.
- [Maps Platform Terms](https://cloud.google.com/maps-platform/terms), §3.2.3: restricciones de scraping, exportación y creación de contenido derivado, incluido trazado de carreteras y edificios.
- [Términos adicionales Maps/Earth](https://www.google.com/help/terms_maps/): restricciones sobre crear o ampliar conjuntos cartográficos sustitutivos.

Un permiso para visualizar contexto no autoriza extraer geometría distribuible.
No se ha encontrado ni activado una vía oficial gratuita que permita importar
esos modelos en el juego. [Consultas verificadas](official-source-research.json)
incluyen URL, fecha, estado HTTP, hashes y fragmentos breves.
