# Diagnóstico GEO-001 y entrega GEO-001.1

Fecha: 20 de octubre de 2026. Proyecto preparado en el checkout existente
`/workspace/MonterreySANDBOX` de `DavrosMTY/MonterreySANDBOX`.

## Resultado principal

**GEO-001 funciona como exportador de demostración. GEO-001.1 ya procesa datos
reales de un sector de 2 × 2 km de Monterrey.** La validación local del pipeline
pasa; la integración Unreal y la compilación Windows permanecen sin ejecutar.

## Paquete recibido

Se inspeccionaron los miembros del ZIP antes de extraerlo, sin rutas que escapen
del directorio de inspección ni enlaces simbólicos. Se conservaron el README
original y el SHA-256 del archivo en `GEO001_PROVENANCE.json`.

Sus **3 pruebas originales pasaron**. La regeneración del demo produjo PNG y R16
idénticos byte por byte a los entregados y ambos coincidieron con los hashes del
manifest original. El error máximo de cuantización original fue
0.0005843956954549867 m. Su propio README identifica correctamente el relieve como
sintético: no representaba las elevaciones reales de Monterrey.

## Mejoras implementadas

| Hallazgo | Cambio y comprobación |
|---|---|
| Solo se probaban cuadrícula, cuantización y NaN en alturas | Suite ampliada a **40 pruebas**, incluidas lectura GeoTIFF, reproyección WGS84→UTM, orientación analítica, escala/offset, unidades, cobertura y NoData |
| Extensiones NaN/inf y coordenadas fuera de la zona no se rechazaban de forma suficiente | Validación finita y de dominio UTM 14N antes de crear salidas |
| Lectura de DEM sin aplicación explícita de escala/offset de banda | Aplicación de ambos y rechazo de unidades verticales no métricas |
| Una única tesela y ninguna prueba de uniones | Mosaico de hasta 8×8 teselas en memoria acotada, una cuantización global, muestras de borde compartidas; cuatro uniones verificadas para el piloto 2×2 |
| Orientación y ubicación quedaban para decidir durante la importación manual | Contrato X=este UTM, Y=sur UTM, Z=arriba; ubicación de actor y cuatro controles por tesela, manteniendo pendiente su prueba dentro de UE |
| Procedencia limitada a una ruta local | URL, consulta OSM, fecha, fecha base OSM, hashes, licencias, datum y avisos de distribución |
| PNG/R16 no contienen CRS | GeoTIFF de referencia con CRS, unidades y etiqueta de datum; verificación contra todas las elevaciones reconstruidas del heightmap |
| Exportación sobreescribía archivos | Rechazo de directorios no vacíos; descargas temporales con límites y limpieza ante errores |
| No había herramienta urbana | Grafo dirigido OSM, división en nodos compartidos, recorte métrico, preservación de etiquetas; edificios simples y multipolígonos con patios y contornos fragmentados |
| Dependencias sin fijar | Python 3.12, entorno virtual, versiones concretas en lockfile, setup repetible y CI geoespacial Linux/Windows |

La validación también comprueba tamaños, PNG contra R16, hashes, puntos de control,
ubicación, georreferencia por centros de píxel, elevaciones y bordes comunes.
Una alteración de los archivos hace fallar el verificador.

## Sector real producido

Centro heredado del paquete: **25.667, −100.310**; EPSG:32614.
La selección es un piloto del centro, no la delimitación metropolitana completa.

| Propiedad | Resultado |
|---|---|
| Fuente de elevación | Copernicus DEM GLO-30, distribución COG AWS 2021 |
| Tesela fuente | `Copernicus_DSM_COG_10_N25_00_W101_00_DEM` |
| Archivo descargado | 41,195,631 bytes; SHA-256 en la ficha de procedencia |
| Modelo | DSM: superficie con estructuras y vegetación, no DTM desnudo |
| Datum vertical | EGM2008, confirmado en manual oficial; no se convirtió |
| Sector | 2,000 × 2,000 metros de cuadrícula UTM |
| Exportación principal | 505 × 505 vértices; separación 3.968253968 m |
| Elevaciones principal | 515.197021484375 a 567.842041015625 m |
| Error máximo de cuantización principal | 0.0004418119788169861 m, aproximadamente 0.44 mm |
| Exportación teselada | 4 × 505² vértices; mosaico 1009²; separación 1.984126984 m; cuatro bordes exactos |
| Tramos OSM recortados | 2,665; incluyen distintos tipos `highway`, también vías no destinadas a automóviles |
| Grafo derivado | 1,903 nodos; 4,194 aristas dirigidas; no es aún navegación de carriles |
| Edificios | 1,136 huellas; tres relaciones multipolígono procesadas, sin omisiones registradas en este extracto |
| Alturas de edificios | Solo 4 etiquetas métricas disponibles; las otras 1,132 quedan desconocidas |
| Fecha base OSM | `2026-10-20T20:08:43Z` |

La precisión de cuantización **no es precisión del terreno**. La resolución de
fuente sigue siendo aproximadamente 30 m y su exactitud local no se validó contra
topografía independiente. El muestreo más denso de las teselas no crea información
nueva. Las huellas OSM tampoco certifican levantamientos ni alturas de fachadas.

## Pruebas y entorno

Se ejecutaron instalación inicial y reinstalación con el script guardado,
`pip check`, la suite completa y la aceptación con fuentes locales reutilizadas.
**40 pruebas pasaron, 0 fallaron, 0 errores, 0 omitidas.** Se comprobaron el demo,
el DEM real, ambos formatos de heightmap, GeoTIFF, mosaicos y conversión OSM real.
`VALIDATION.json` resume la corrida final; el paquete conserva JUnit y logs.

Se identificó inicialmente un HTTP 403 del proxy para fuentes externas. Los
dominios requeridos se guardaron y posteriormente funcionaron las adquisiciones
de DEM y OSM y la lectura de los documentos oficiales. El texto ODbL se obtuvo de
la reproducción SPDX por rechazo HTTP del servidor de la licencia.

El host es Linux x86_64. GDAL, Python, NumPy, Rasterio, PyProj, Pillow, Shapely,
Matplotlib y Pytest están operativos. No hacen falta servicios persistentes.
Se guardaron `install_script`, `start_skill` y dominios de red en el borrador del
entorno. Guardar el borrador no demuestra publicación ni restauración en otra tarea.

## Límites y siguiente trabajo

**No hay Unreal Editor instalado**. `tools/check_unreal.py` lo informa con salida
2. El descriptor `.uproject` es un esqueleto: no hay mapas, Landscape creado en el
editor, mallas urbanas, World Partition configurado, materiales, vehículos ni juego
compilado. No se han probado Windows ni el workflow remoto de GitHub Actions.

La orientación definida matemáticamente sigue necesitando comprobación dentro de
Unreal con los puntos de control. El siguiente hito de integración requiere un
runner con UE5 licenciado y herramientas Windows; no exige al supervisor programar
ni ejecutar comandos. El desarrollo geoespacial puede continuar aquí con DTM/LiDAR,
extracción PBF regional y preparación de mallas, conservando datos desconocidos.

Antes de extender a toda la metrópoli deben decidirse límites, fuente de mayor
resolución y presupuesto de distorsión: UTM introduce aproximadamente 0.019 % en
el centro. No se han adquirido recursos comerciales ni publicado el repositorio.
