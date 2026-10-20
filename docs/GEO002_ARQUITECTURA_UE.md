# Integración preparada para UE 5.6

Estado: **fuentes y automatización preparadas; sin compilar ni ejecutar en Unreal**.
El host Linux no tiene editor ni toolchain Windows/Epic. Las imágenes de esta
entrega son renders de Blender. Las referencias primarias consultadas, con URL,
versión y hash, figuran en `GEO002_REFERENCES.json`.

## Coordenadas e intercambio

El generador trabaja en metros, X=este UTM, Y=norte UTM, Z=arriba, con cero vertical
del datum EGM2008. La geometría GLB usa la convención glTF: X=este, Y=arriba,
Z=sur, sistema derecho, metros. La transformación se almacena en el manifest.
Blender convierte glTF a sus ejes Z-arriba al importar; se comprobaron los límites
globales y el número real de triángulos antes de renderizar.

OBJ para UE contiene valores numéricos en centímetros, X=este, Y=sur, Z=arriba.
Se invierte el orden de triángulos al reflejar Y. Cada archivo tiene origen local
en el centro de su celda horizontal y Z=0 del datum. `position_unreal_cm` coloca
el actor; `bounds_local_unreal_cm` permite detectar conversiones involuntarias.
Los materiales MTL contienen colores de blockout, sin texturas externas.

Las 64 celdas de ciudad y las 64 de terreno se exportan por separado. Así el modo
Landscape no duplica la superficie del DSM. El modo `static_mesh` importa las
128 celdas y permite revisar geometría antes de activar Landscape. Las celdas del
generador miden 250 m; esto no prueba ni impone el tamaño de streaming del motor.

## Automatización implementada

`tools/run_unreal_geo002.py` detecta un editor y host Windows apropiados. Si faltan,
escribe un recibo de bloqueo y termina con código 2. No simula una compilación.
Con un runner adecuado, prepara estos pasos:

1. Ejecutar `Build.bat` para `MonterreyOpenWorldEditor`, Win64, Development.
2. Ejecutar `Content/Python/import_geo002.py` con el editor. El script verifica
   hashes, preserva contenido existente, importa OBJ mediante `AssetImportTask`
   y `FbxFactory`, combina por celda y comprueba sus dimensiones numéricas.
3. Intentar habilitar Nanite en las mallas urbanas. Registrar cada resultado;
   una opción de importación no demuestra que Nanite funcione ni rinda bien.
4. Importar el heightmap mediante el plugin editor `MonterreyGeo`, usando la
   firma documentada de `ALandscapeProxy::Import`, 505² vértices, 2 subsecciones
   y 63 quads por sección. Leer alturas de control desde Landscape y comprobar
   transformación y cuantización en centímetros.
5. Importar los 1,136 registros `pcg_buildings.csv` como DataTable tipada. No se
   ejecuta ni se afirma que exista ya un grafo PCG de decoración.
6. Guardar el mapa y convertir una copia `_WP` mediante
   `WorldPartitionConvertCommandlet`, conservando el mapa de importación.
7. Cargar el mapa convertido y comprobar con API nativa que tiene World Partition.
8. Opcionalmente ejecutar `WorldPartitionHLODsBuilder`; registrar sus logs y código
   de salida. No generar HLOD hasta validar visualmente las mallas y materiales.

Los scripts conservan logs y recibos JSON. Una API que cambie de firma o una
conversión de ejes distinta debe producir un error, no un falso resultado válido.
El módulo C++ y sus llamadas necesitan una primera compilación real en UE 5.6;
la consulta de documentación y el análisis sintáctico Python no sustituyen esa
prueba. Tampoco se ha validado todavía carga de todas las regiones, colisión ni
conversión de Landscape a proxies de streaming en el mapa final.

## World Partition, Nanite, Lumen, PCG y HLOD

El proyecto incluye módulos Runtime/Editor mínimos y un plugin de herramientas,
sin vehículos, personajes ni misiones. El plugin de PCG y GeoReferencing está
declarado; el contrato UTM se conserva en manifests, no se afirma que un actor
GeoReferencing ya esté configurado y probado dentro del mapa.

`DefaultEngine.ini` solicita Lumen, campos de distancia y sombras virtuales.
No contiene una certificación de rendimiento ni shaders compilados. Nanite se
solicita para mallas de ciudad; su configuración efectiva queda en el recibo UE.

`Content/Maps/GEO002.ini` prepara una capa HLOD MeshMerge, celdas HLOD de 500 m y
alcance de 2 km, siguiendo el formato documentado del conversor. Son valores
iniciales para evaluar, no presupuestos de rendimiento medidos. Agrupar por celda
reduce objetos iniciales; posteriores generaciones podrán separar edificios
interactivos y conservar sus identificadores mediante el manifest y la DataTable.

Las fachadas modulares y cubiertas son geometría y colores repetibles de blockout.
PBR, vegetación, mobiliario y monumentos se añadirán como capas posteriores, con
su procedencia y licencias. Ningún dato ausente se convierte en un hecho observado.
