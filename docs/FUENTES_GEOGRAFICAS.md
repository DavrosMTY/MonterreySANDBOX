# Fuentes geográficas y derechos

Estado comprobado el 20 de octubre de 2026. Tras una denegación inicial del proxy,
se guardaron los dominios necesarios y posteriormente funcionaron las descargas
HTTPS de Copernicus, sus términos y manual, la página de derechos OSM y Overpass.
Se descargaron elevaciones y vías reales del sector piloto. URLs y hashes de los
documentos revisados están en `sources/legal-evidence.json`.

| Fuente | Uso previsto | Resolución / precisión | Derechos y estado |
|---|---|---|---|
| [Copernicus GLO-30](https://registry.opendata.aws/copernicus-dem/) | Relieve inicial reproducible | DSM de unos 30 m; incluye estructuras/vegetación, no terreno desnudo | Licencia pública GLO-30-F leída: reproducción, distribución, adaptación y combinación sin cargo, con avisos de origen, derivados y responsabilidad. Texto aplicable conservado en `sources/COPERNICUS_GLO30_LICENSE.txt`. |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Ejes viales, huellas, nombres y etiquetas | Cobertura y exactitud variables; no garantiza carriles, alturas ni actualidad | ODbL 1.0, atribuir «© OpenStreetMap contributors». Las bases derivadas distribuidas pueden tener obligación de compartir bajo ODbL; distinguirlas de un producto visual. Extracto real descargado. |
| [INEGI, relieve continental](https://www.inegi.org.mx/temas/relieve/continental/) | Candidato preferente para terreno nacional y LiDAR disponible | CEM y productos de distintas resoluciones; verificar cobertura local, fecha, DTM/DSM y ficha de cada producto | Revisar [Términos de libre uso](https://www.inegi.org.mx/inegi/terminos.html) y metadatos del producto antes de integrar. No descargado ni validado aquí. No se asume datum vertical. |
| [NASA/USGS SRTM](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1) | Respaldo de relieve | Aproximadamente 30 m, datum vertical EGM96 en SRTM; terreno/superficie según producto | Verificar producto oficial y condiciones concretas. Algunos portales exigen autenticación. No probado ni necesario para las pruebas locales. |

## Selección inicial implementada

`GeoPipeline.acquire` calcula la tesela Copernicus que contiene el centro:
`Copernicus_DSM_COG_10_N25_00_W101_00_DEM`. Descarga HTTPS limitada a 150 MiB,
valida formato, conserva URL, fecha UTC, ETag y SHA-256. El hash registra identidad;
no se presenta como firma del proveedor. La adquisición OSM solicita como máximo
un cuadrado de 5 km, registra consulta y fecha base de datos, y rechaza errores
Overpass incluso con respuesta HTTP exitosa. No hay sustitución sintética silenciosa.

Copernicus GLO-30 usa alturas ortométricas EGM2008: confirmado en Product Handbook
5.0, §1.2.1; unidades en metros y RasterPixelIsPoint en §1.2.2. No convertir a EGM96,
elipsoide o datum de INEGI sin transformación y rejillas verificadas. El exportador
conserva el datum declarado y rechaza contradicciones con el registro de origen.

Se conserva la licencia ODbL íntegra reproducida por SPDX, pues el servidor
opendatacommons.org devolvió HTTP 403; la página oficial de derechos de OSM sí fue
consultada. El paquete incluye el extracto fuente OSM y sus derivados identificados
como ODbL 1.0. Los avisos de Copernicus acompañan cada terreno real exportado.

La consulta OSM emplea una envolvente WGS84 del cuadrado UTM; el convertidor
recorta al cuadrado métrico exacto. Áreas metropolitanas completas requerirán
extractos regionales PBF y un importador dedicado, no consultas Overpass masivas.

No utilizar capturas, fotogrametría ni modelos extraídos de Google Maps/Earth u
otros servicios comerciales sin derechos expresos. Para materiales, señalética y
fachadas se necesitarán fuentes propias o con licencia adecuada.

## Límite de fidelidad

Interpolar un DSM de 30 m a vértices cada 4 m **no añade detalle real**. Es útil para
una primera base territorial; no resuelve banquetas, peraltes, baches, pasos a
desnivel, fachadas o conducción realista. Para esas capas se requieren DTM/LiDAR,
levantamientos y geometría de ingeniería. Las alturas de edificios ausentes
permanecen desconocidas; no se convierten plantas a metros sin una política explícita.

La licencia del código del ZIP original no fue proporcionada. Se registra su
procedencia y no se inventa una autorización de redistribución pública del proyecto.
