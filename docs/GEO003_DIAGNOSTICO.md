# GEO-003 / WORLD-001 — diagnóstico de entrega

Fecha: 2026-10-20 UTC. Sector centro de Monterrey de 2 × 2 km.
Estado: **graybox candidato para integración; aceptación offline con incidencias**.
No se afirma mundo completo conducible ni funcionamiento dentro de Unreal.
Repositorio modificado localmente, sin push/publicación remota ni servicios de pago.

## Qué se ejecutó

Se auditó GEO-002 y se ejecutaron sus 60 pruebas antes de los cambios. Se conservan
el DEM original, las fuentes urbanas, la georreferencia y las salidas GEO-002 v4.
La ruta nueva `GeoPipeline.world` reutiliza las herramientas GIS y añade el ajuste
WORLD-001; `GeoPipeline.city` mantiene GEO-002 como comportamiento por defecto.

El sector refinado se generó desde los datos reales retenidos. Se reabrieron el
GLB y todos los OBJ, se comprobaron alturas contra las mallas, y se renderizaron
tres vistas con Blender Cycles CPU, 64 muestras, 1440 × 960. No son imágenes IA.
El render conserva versión de Blender, hash del modelo, cámaras y hashes PNG/.blend.

La aceptación final está en `artifacts/geo003-acceptance-zxwe2p6n/`: 72 pruebas,
0 fallos, 0 errores y 0 omitidas; QA de exportaciones y auditoría por carretera.
También se ejecutó el flujo CI sintético completo en Linux desde un directorio
nuevo: generación DEM, OSM fixture, WORLD-001, QA GLB/OBJ y QA geográfico.
Windows y GitHub Actions remoto no se ejecutaron. `pip check` no detectó conflictos.

## Cambios implementados

**Perfiles viales conjuntos.** Un problema disperso de programación lineal ajusta
28,356 variables con 115,149 desigualdades. Cada nodo OSM compartido usa una sola
variable Z. Se conservan XY, IDs y las 4,194 aristas dirigidas; no se crean enlaces
por proximidad ni entre niveles al cruzar geometrías. Se incluyen quiebres del
trazado, muestreo de hasta 5 m y cruces entre niveles. La altura permanece estimada.

| Categoría vial | Límite longitudinal del perfil |
| --- | ---: |
| motorway/trunk y sus enlaces | 8 % |
| primary/secondary y sus enlaces | 10 % |
| tertiary/residential/service/living_street y resto motorizado | 12 % |
| senderos, ciclovías y áreas peatonales | 35 % |
| steps, aún representados como rampas | 100 % |

En los **perfiles** quedan 0 candidatos motorizados sobre 15 % (GEO-002 tenía 195).
Esto no equivale a corregir todos los triángulos: la lectura de superficie aún
marca 23 tramos por pendientes locales exportadas, 30 por desviación >8 cm y
336 por cobertura incompleta/recorte de edificios, con solapamiento entre causas.
De los motorizados, uno (`way/570044971/1106`) aún alcanza 15.52 % al muestrear la
malla; está excluido de la ruta candidata. Los 335 perfiles >15 % del contador
histórico global son peatonales/escalones, no vías candidatas motorizadas.

**Capas no destructivas.** `correction_layers/elevation_delta_m.tif` es un delta
aditivo; `corrected_DSM.tif` es su aplicación. Los GeoTIFF retienen EPSG:32614,
transformación de píxeles/vértices y datum. La reconstrucción base + delta coincide
a 0.00003052 m por almacenamiento float32. Hay 1,605 corredores de corrección,
108,318 vértices modificados de 255,025 (42.47 %), transición de 6 m tras el margen
vial y delta máximo absoluto 6.689 m. Cero vértices fuera de los corredores cambian.
El solape de corredores en un centro urbano explica su cobertura: no es un filtro
global del relieve. El DSM corregido **no es un DTM nuevo ni un levantamiento**.

**Terreno e infraestructura.** Se sustituyen 838,939.53 m² de terreno bajo las
superficies de vías/banquetas por sus losas; los faldones enlazan con la altura
local del terreno corregido. Así el raster más grueso no atraviesa la calzada.
Esto es una sustitución geométrica local identificada, no un cambio del DEM base.
Las huellas de edificios bloqueantes se conservan; los recortes de vías se auditan.

**Túneles.** La máscara de excavación ocupa 17,101.60 m² e incluye los segmentos
`highway` con túnel explícito, tanto motorizados como peatonales. Se elimina el
terreno sobre esos corredores y se añaden pisos, techos de los motorizados y
paredes laterales con aperturas en conexiones/portales. Es una solución de zanja
cubierta equivalente, no una recreación topográfica de portales, drenaje o ingeniería.
Los túneles peatonales conservan suelo y paredes, sin certificar techo continuo.
Las etiquetas OSM de gálibo se conservan como datos, sin inferir que sean mediciones
de techo. No se permiten conversiones silenciosas de túnel a calle de superficie.

En las mallas exportadas hay 0 m² de terreno dentro del núcleo de máscaras de
excavación y sustitución, excluyendo 1 mm de borde por precisión de intercambio.
El solape bruto en el borde de túneles es 0.2212 m² distribuido en sus perímetros;
no se presenta como cero exacto. Las 64 celdas coinciden en sus bordes a 1 mm.

**Graybox y segmentación.** Se quitan filas/paneles de fachadas manteniendo las
huellas y 4 patios, alturas con procedencia y 1,136 edificios. La base sobre DSM
corregido sigue siendo procedural. Se exportan 279 assets por sistema/celda,
además de 128 OBJ de compatibilidad (407 OBJ leídos de vuelta). Sistemas:
Landscape estático, Roads, Sidewalks, Bridges, Tunnels y Buildings. Hay prototipo
compartido y 1,136 transforms para representación distante; no es HISM ejecutado.

## Métricas del modelo

| Métrica | Resultado |
| --- | ---: |
| Triángulos totales | 1,077,198 |
| Vértices en generación | 617,325 |
| Piezas GLB | 2,673 |
| Sólidos cerrados comprobados | 2,609 |
| Superficies abiertas de terreno, intencionadas | 64 |
| Edificios / tramos OSM | 1,136 / 2,665 |
| Segmentos superficie | 2,475 |
| Segmentos bridge / elevated_inferred | 63 / 13 |
| Segmentos tunnel / depressed_inferred | 110 / 4 |
| Máximo error de coordenadas en GLB | 0.000003785 m |
| Error vertical máximo en nodos OSM compartidos | 0 m |
| Cambio en XY de los trazados fuente | 0 m |

Los números de bridge/tunnel son **segmentos**, no estructuras únicas.

| Sistema | Triángulos |
| --- | ---: |
| Terreno estático recortado | 531,234 |
| Edificios graybox | 20,636 |
| Calzadas | 230,924 |
| Banquetas/senderos | 255,860 |
| Puentes/elevados | 14,180 |
| Túneles/paredes/techos | 24,364 |

Reducción total respecto a 1,895,648 triángulos de GEO-002: 43.18 %. El GLB ocupa
24,161,568 bytes. No es una medición de FPS, VRAM ni draw calls en UE.

## Incidencias y ruta candidata

La auditoría clasifica 2,267 tramos como candidatos geométricos offline y 398 como
pendientes de refinamiento. De 1,686 candidatos motorizados, **1,589 pasan estos
controles discretos y 97 quedan excluidos**. Un muestreo de centrolinea no demuestra
anchura utilizable, continuidad de colisión entre todos los triángulos, ni paso de
un vehículo o cápsula. Las aceras no cuentan con certificación de accesibilidad.

De 201 cruces entre niveles, 186 tienen ambas superficies presentes: mínimo de
separación de tapas 7.11996 m, sin solapes de piso detectados en esos puntos y sin
gálibo estimado bajo 5 m. Otros 15 tienen una superficie ausente; se marcan sus
24 tramos incidentes, sin aprobarlos por interpolación. Algunas sendas se eliminan
al solaparse con calzadas o edificios. Una calzada visible allí no demuestra que
exista la pasarela/senda del nivel solicitado. Esto evita falsos positivos y falsos
certificados de separación. No se certifican volúmenes completos ni estructuras.

El ajuste registra un cruce que no logra los 7.2 m nominales: túnel de servicio
`way/1262706308/2318` y Ciclovía Macroplaza `way/1322900353/2626`, déficit 3.06777 m.
No se desplaza el trazado ni se cambia el grafo para ocultarlo. Queda en cuarentena.
Se necesitan mejor información vertical y resolución de geometría local.

Se preparó una ruta dirigida **de 1,497.832 m**, usando sólo las 1,589 vías que pasan
los controles offline y respetando sentidos del grafo fuente. Incluye 130 sondas
para trazas nativas UE posteriores. Ruta y sondas están en la carpeta `route/` de
la evidencia. No se condujo, no se barrió una cápsula y no se probó física de ruedas.

## Unreal: preparado y explícitamente no verificado

Proyecto base UE5.6, módulo runtime, plugin editor C++, UMonterreyWorldData,
importador con hashes/ejes/bounds, colisión estática compleja como simple, script
de build/importación/World Partition y trazas verticales nativas opcionales.
Nanite se clasifica por candidato pero queda desactivado hasta revisar fallback
de colisión. PCG dispone de registros tipados; HLOD tiene configuración inicial.

WORLD-001 exige **terreno estático excavado**: el importador rechaza Landscape
intacto, que taparía los túneles. Las llamadas UE están revisadas pero **no
compiladas ni ejecutadas**. `tools/run_unreal_geo003.py` produjo un recibo blocked,
código 2, por falta de editor UE5.6 licenciado y toolchain Windows. No hay .umap,
PCG/HLOD construidos, Nanite/Lumen probado, cooking ni build Windows validado.
No se deriva un certificado de colisión del hecho de exportar categorías.

## Siguiente prioridad técnica

Corregir primero los 97 tramos motorizados excluidos: representar quiebres en
límites/celdas sin picos de triangulación, resolver recortes que estrechan pasos,
plazas peatonales OSM `area=yes` aún tratadas como recorridos perimetrales y
cruces con superficies ausentes. Requiere mejorar el mallado y contrastar geometría
con DTM/control vertical antes de sustituir supuestos por elevaciones reales.
INEGI CEM/DTM/LiDAR sigue siendo una fuente candidata, no adquirida en esta entrega.
Después, ejecutar el runner en UE5.6 Windows y verificar colisión, cápsula/ruedas,
portales, streaming y HLOD con recibos reales. No se priorizan tráfico, misiones o NPCs.

La configuración cloud reutilizable se guarda como borrador; no equivale a
publicación del entorno ni demuestra restauración en una tarea nueva. El ZIP
incluye el raster de referencia original del piloto, delta, extracto OSM, avisos
Copernicus/ODbL y hashes de cada archivo. No incluye el DEM completo de un grado,
la virtualenv ni las iteraciones intermedias descartadas de esta revisión.
