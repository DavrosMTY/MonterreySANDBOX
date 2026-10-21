# Auditoría GEO-002 antes de WORLD-001

Estado de entrada: Data/city/geo002_v4, 1,136 edificios, 2,665 tramos,
1,895,648 triángulos; suite previa ejecutada: 60 pruebas aprobadas.
Los entregables anteriores permanecen conservados.

Se mantienen adquisición con procedencia y checksum, reproyección EPSG:32614,
EGM2008 sin conversión vertical, exportación R16/PNG/TIFF, grafo OSM sin conexiones
por cruces geométricos, huellas con patios, alturas con procedencia y lector QA
GLB/OBJ. Los módulos geo001, acquire, urban, validate y los contratos
de coordenadas siguen siendo la base. buildings3d conserva su generación detallada y añade la variante graybox.
city y roads3d incorporan una ruta opcional para WORLD-001; GEO-002 conserva su comportamiento por defecto.

La horizontal es coherente numéricamente, no certificada por levantamiento.
1 metro de cuadrícula proyectada equivale a 100 unidades Unreal; la deformación
UTM continúa registrada. GLB usa metros, OBJ usa centímetros y pivotes locales.

Elevación y jugabilidad pendientes: el DSM de ~30 m incorpora objetos y vegetación;
195 tramos candidatos motorizados superaban 15 %. Los perfiles locales de puente
podían generar rampas bruscas. Los túneles tenían piso y techo pero el terreno no
estaba excavado. Faltaban comprobaciones conjuntas de continuidad vertical.
Las banquetas, anchuras, alturas de mayoría de edificios y fachadas son estimadas.
Las huellas bloquean ciertas superficies viales; recortarlas evita sólidos en
edificios pero puede estrechar/cortar rutas. El grafo lógico no acredita paso físico.

Riesgos de importación: los OBJ urbanos mezclaban sistemas en una celda; no había
política de colisión cocinada. Importar Landscape intacto taparía los túneles.
Nanite no sustituye colisión y usa representación fallback para ciertas consultas.
Las llamadas UE, el módulo C++ y el convertidor World Partition requieren ejecución
real en UE 5.6 con toolchain Windows; aquí no hay editor ni compilador UE.

WORLD-001 añade un ajuste de perfiles compartido, capas raster aditivas locales,
máscara vectorial de excavación y terreno estático recortado, exportación por
sistema/celda y comprobaciones separadas de grafo, perfiles y malla exportada.
Todo ajuste artificial queda etiquetado como procedural, sin modificar el DEM base.
No se adquiere un nuevo DTM en esta entrega ni se interpreta el DSM corregido como tal.
