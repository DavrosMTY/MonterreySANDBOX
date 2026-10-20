# GEO-002 — primera representación 3D de Monterrey

Entrega del 20 de octubre de 2026. Estado: **modelo procedural generado, exportado,
leído de nuevo y renderizado en Blender**. La integración UE5/Windows está preparada
en código, pero bloqueada por ausencia de editor y toolchain en este host.

## Resultado verificable

| Componente | Resultado |
|---|---|
| Sector | 2 × 2 km de cuadrícula UTM del centro de Monterrey, heredado de GEO-001.1 |
| Datos | Copernicus GLO-30 DSM y extracto OSM real, sin sustituir por relieve ficticio |
| Edificios | 1,136 partes; cuatro patios preservados |
| Alturas | 4 etiquetas métricas OSM, 169 alturas inferidas desde plantas, 963 valores de clase configurables |
| Clases | 115 residenciales, 92 comerciales, 73 industriales, 49 cívicas, 18 cubiertas/canopies, 789 usos desconocidos |
| Vías de origen | 2,665 tramos, no carriles individuales; 4,194 aristas originales conservadas |
| Niveles | 63 tramos puente, 110 túnel, 13 elevados inferidos por layer y cuatro deprimidos inferidos |
| Geometría | **1,895,648 triángulos**, 960,342 vértices entre partes, 2,576 partes |
| Topología | 2,512 sólidos cerrados con volumen positivo; 64 superficies abiertas de terreno intencionales |
| Exportación | GLB de 32,894,836 bytes; 64 OBJ de ciudad y 64 OBJ de terreno, con MTL |
| Intercambio | Error máximo medido de coordenadas al volver a leer GLB: 0.0000037842 m |
| Pruebas | **60 aprobadas**, sin fallos, errores ni omitidas |
| Imágenes | Tres renders reales: aérea, calle y elevada; Blender 4.3.2 / Cycles CPU |

`GEO002_VALIDATION.json` contiene la aceptación final. JUnit, logs, cámaras,
hashes y auditorías completas se incluyen en el ZIP. No se hizo push ni publicación
remota del repositorio. La CI Windows está definida; aquí se reprodujo su flujo
geométrico en Linux, no se ejecutó GitHub Actions ni Windows.

## Auditoría de GEO-001.1 y precisión

Se conservó el exportador, el lector de datos reales y sus 40 pruebas previas.
Las 20 pruebas nuevas cubren extrusión, patios, volúmenes, fachadas, cimentación,
anchos y niveles, controles interiores de triangulación, escala, ejes, intercambio
GLB/OBJ, terreno y recortes contra edificios.

La conversión WGS84 → UTM y las huellas locales coinciden dentro de
1.9 × 10⁻⁹ m numéricos. Esto mide coherencia del cálculo, **no precisión de OSM**.
Los lados norte y oeste de 2,000 m de cuadrícula miden aproximadamente 2000.373 m
y 2000.367 m geodésicos. Se conserva EPSG:32614 y su factor 0.9998134481, sin
cambiar silenciosamente el contrato espacial ni afirmar una escala geodésica exacta.

La fuente vertical es EGM2008, sin conversión. El DSM tiene unos 30 m de resolución
nativa e incluye estructuras/vegetación. Las bases y cotas viales son aproximaciones
sobre esa superficie; no se han contrastado con DTM/LiDAR ni controles topográficos
independientes. Densificar la malla no aporta detalle geográfico nuevo.

## Edificios

El generador convierte las huellas a metros este/norte/arriba y las extruye con
triangulación restringida. Conserva polígonos cóncavos, anillos interiores e IDs de
vías y relaciones OSM. Las fachadas se subdividen en módulos de antepecho, ventana
y dintel; las cubiertas son tapas planas de blockout, sin inventar arquitectura
observada. Los colores de vértice y materiales MTL son datos procedurales.

Las alturas siguen esta prioridad: etiqueta `height`; después `building:levels`
por altura de planta configurable; finalmente valor de clase. El uso no conocido
se mantiene como `unknown`. También se conserva `building:min_level`, el estado
de construcción y las demás etiquetas. Las 18 huellas `building=roof` se tratan
como cubiertas elevadas delgadas, no como edificios llenos hasta el suelo; sus
soportes estructurales no están reconstruidos.

Las bases emplean un percentil del DSM de perímetro, marcado como estimación.
La cimentación se extiende hacia abajo hasta alcanzar el punto más bajo muestreado:
esto corrigió 245 huecos de perímetro observados en el primer prototipo. Las alturas
superiores y posiciones originales no se mueven para disimular esas pendientes.
La geometría derivada usa una cuadrícula numérica de 0.1 mm para evitar degeneración;
los datos de entrada permanecen intactos.

## Calles, banquetas, intersecciones y niveles

Se generan losas cerradas para calzadas y pasos peatonales; los anchos provienen de
etiquetas cuando existen, de carriles por ancho configurable o de clases de vía.
En este extracto no hay etiquetas `width`: todos los anchos son derivados o
procedurales. Las banquetas usan las etiquetas disponibles y reglas urbanas
identificadas como estimación. Los escalones OSM se representan como superficies
inclinadas, todavía sin peldaños individuales.

Las superficies del mismo nivel se unen para formar intersecciones geométricas.
Los IDs OSM determinan el grafo; un cruce en planta no añade conexiones nuevas.
Se conservan sentido, layer, bridge/tunnel, acceso y procedencia. No se generan
carriles individuales ni restricciones de giro; el grafo no es aún un navegador.

Los anchos aproximados invadían algunas huellas: se recortaron 8,038.31 m² de
superficies derivadas, sin desplazar edificios ni ejes fuente. No quedan solapes
proyectados de calzadas/banquetas de superficie con los edificios que bloquean el
suelo. Algunos pasos quedan estrechos o interrumpidos; no se afirma que el recorte
reproduzca el derecho de vía real. Las cubiertas y edificios elevados permiten
pasos inferiores, siguiendo su clasificación.

La primera auditoría halló cruces a distinto nivel demasiado próximos. Se
introdujeron restricciones verticales procedurales con separación nominal de
superficies de 6.1 m y se insertaron los puntos críticos en la triangulación de
las tapas. Sin esos vértices, una curva correcta perdía altura al hacerse malla.

La auditoría final revisa 201 cruces de perfil y **186 puntos con ambas superficies
exportadas presentes**. En esos 186 puntos hay cero solapes potenciales de losas,
cero separaciones inferiores a 5 m y un mínimo medido de **6.01984 m entre tapas
superiores**. Los otros 15 puntos no tienen ambas superficies tras la generación y
se registran como no comprobados, no como aprobados. Esto no es una comprobación
de gálibo volumétrico de toda la estructura ni una certificación de ingeniería.

## Errores y limitaciones pendientes

- **195 tramos motorizados y 170 peatonales superan 15 % de pendiente muestreada**.
  El ajuste al DSM, las rampas cortas y las restricciones de cruce no bastan para
  una red conducible realista. Se necesitan DTM y perfiles viales mejor informados,
  transición por cadenas completas y una nueva política de nivelación. No se
  aplanan alturas en silencio para ocultarlo.
- Los túneles tienen piso y losa superior, pero no portales excavados ni interiores
  transitables completos. El terreno no tiene excavaciones. Los puentes aún no
  incluyen ingeniería de apoyos, peraltes ni estructura real.
- No se han certificado todas las colisiones entre pares de mallas ni la exactitud
  absoluta de altitudes. La prueba de topología certifica cada sólido, no la unión
  booleana de toda la ciudad. Las relaciones espaciales fuente también pueden
  contener inconsistencias.
- No se han reconstruido fachadas reales, monumentos, vegetación, señalización,
  mobiliario o materiales fotográficos. No hay vehículos, personajes, tráfico ni
  misiones; esta etapa se concentra en el mundo tridimensional.
- El plugin C++, la importación Landscape y las APIs de editor están **sin compilar
  y sin ejecutar**. No hay mapa `.umap` creado aquí, gameplay ni ejecutable Windows.
  World Partition, Nanite, Lumen, PCG y HLOD tienen configuración y automatización
  preparadas, no validación dentro del motor. Ver `GEO002_ARQUITECTURA_UE.md`.

## Rendimiento y reproducibilidad

En esta máquina, la geometría final tardó aproximadamente 34.2 s y su generación
más exportación 47.2 s. La lectura y QA completa de GLB y 128 OBJ tardó unos 7.7 s.
Los tiempos de render reales, muestras, resolución y cámaras están en
`render_evidence.json`; se usaron 8 hilos CPU, 64 muestras y 1440×960 píxeles.
El denoiser no está disponible en este Blender y no se utilizó. No se usaron
imágenes generadas por IA, ni se presentaron estos renders como imágenes de UE.

`tools/run_geo002.py` reproduce pruebas, construcción o reutilización verificada,
QA geométrica, auditoría geográfica y render. Las salidas se crean en directorios
nuevos; los renders reutilizados deben coincidir con el hash del modelo actual.
`tools/package_geo002.py` crea el ZIP con un índice SHA-256 por archivo.

La configuración cloud guarda instalación y arranque reutilizables. Su publicación
y restauración en otra tarea no se han probado. El siguiente hito viable combina
mejor terreno y nivelación vial con la ejecución automática del importador en un
runner Windows con UE5 licenciado; no requiere que el supervisor programe.
