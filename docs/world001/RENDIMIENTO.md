# Rendimiento y crecimiento de WORLD-001

El piloto mantiene 2 km × 2 km; 8 × 8 celdas de 250 m. Los sistemas se exportan
por separado, 279 OBJ/MTL para importación principal. Los 128 OBJ de compatibilidad
no se deben importar además: duplicarían el mundo.

Hay 1,077,198 triángulos totales frente a 1,895,648 previos, reducción 43.18 %.
Edificios: de 986,208 a 20,636 triángulos al omitir módulos/fachadas subdivididas,
con huellas y patios conservados. Las fachadas detalladas siguen disponibles en
GEO-002; no se usó una reducción ciega que alterara el contorno geográfico.

Se mantienen las muestras de terreno; no se inventa detalle a partir del DSM
nativo de ~30 m. La excavación/sustitución usa las muestras originales corregidas
y triangulación local. La altura de vértices nuevos se interpola sobre el plano
del triángulo de origen, evitando discontinuidades entre celdas.

`METRICAS_CELDAS.csv` registra triángulos, vértices, partes, bytes y bounds por
sistema/celda. El asset de mayor coste es Sidewalks (4,5), con 10,280 triángulos.
Los edificios se asignan por pivote y conservan bounds completos; no se cortan
fachadas artificialmente en cada borde. No hay una garantía de 250 m de tamaño
para todo edificio: se debe usar bounds al decidir streaming.

El solver usa matrices dispersas y HiGHS, sin optimizar una matriz densa de
28,356². Las consultas geométricas usan STRtree y geometrías preparadas; las
pruebas de contención de vértices críticos se vectorizan. La generación real de
geometría tomó ~272 s; la cifra de ~281 s incluye exportación básica, no toda
la fase adicional por sistemas. Estas medidas son de este runner CPU, no FPS.
La validación final conserva tiempos de QA, y el render ~177 s para tres vistas.

Estrategia implementada/preparada:

- Terreno/vías cortados por celda, pivotes locales y Z absoluta para precisión.
- Colisión estática separada por sistema; la simulación del vehículo no usa estos
  meshes como cuerpos físicos móviles.
- Prototipo distante unit-box compartido (12 triángulos) y 1,136 transforms, clase,
  tamaño y SourceId. Scale es adimensional; la caja de 1 m mide 100 cm en UE.
  Son proxies de bounds, sin colisión; no sustituyen huellas fieles cerca del jugador.
- Fuentes tipadas PCG disponibles, sin afirmar instancing/HISM ejecutado.
- Nanite marcado candidato para edificios/puentes, desactivado inicialmente hasta
  probar fidelidad y coste de colisión fallback. Nanite no arregla perfiles viales.
- Configuración World Partition RuntimeSpatialHash; HLOD MeshMerge a 500 m con
  rango inicial 2 km. Capas por sistema descritas como metadatos de exportación;
  la creación/asignación efectiva de capas específicas queda por probar en editor.

Antes de ampliar: medir FPS CPU/GPU, draw calls, memoria, cocinado, carga/descarga,
colisión y HLOD dentro de UE, definir presupuesto para PC objetivo y probar una
ruta real con streaming. No extrapolar la aprobación de archivos a esos resultados.
Se debe adquirir DTM adecuado y ampliar en sectores con procedencia/LOD coherente,
sin descargar o generar toda la metrópoli de golpe.
