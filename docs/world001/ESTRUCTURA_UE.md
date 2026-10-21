# Preparación de Unreal Engine 5.6 / Windows

El editor UE y su toolchain no están disponibles. El código C++, sus UHT y las APIs
Python son preparación revisada, todavía sin compilación ni ejecución de Unreal.
`tools/run_unreal_geo003.py` detecta el bloqueo y produce recibo con estado blocked,
exit 2. En un runner Windows con UE_EDITOR, compila el módulo de juego y plugin,
importa, verifica ejes y medidas, guarda mapa, convierte a World Partition y verifica
la partición. `--build-hlod` ejecuta el constructor HLOD sólo con editor disponible.
No hay .umap, .uasset cocinados ni ejecutable jugable en esta entrega.

Convenciones para assets generados:

| Carpeta /Game/WORLD001 | Contenido / política |
| --- | --- |
| Landscape | Terreno estático excavado, celdas 250 m; NO Landscape intacto |
| Roads | Superficies y sólidos, jerarquía arterial/collector/local en semántica |
| Sidewalks | Banquetas y senderos, escalones aún aproximados por rampas |
| Bridges | Puentes y elevados por capa; alturas procedurales |
| Tunnels | Piso, techo, paredes laterales estimadas y máscara de huecos |
| Buildings | Huellas reales, alturas etiquetadas, bloqueos estáticos |
| DataAssets | UMonterreyWorldData con origen UTM, datum, hash y escala |
| PCG | Puntos tipados para futuras reglas; no grafo PCG ejecutado |
| Materials | Paleta MTL/vertex colors; no texturas reales |
| HLOD | Capas de agregación por sistema; revisar y generar con editor |
| WorldPartition | Configuración y recibos de conversión; RuntimeSpatialHash |

Los OBJ se segmentan por sistema y celda con pivote XY local y Z absoluta EGM2008.
Una huella grande se asigna por pivote: el tamaño real puede superar 250 m; el
runtime hash considera bounds. No cortar edificios evita grietas en fachadas.
Terreno y vías se cortan por celda. Las categorías no se mezclan en un solo asset.

Colisión preparada: UBodySetup complejo como simple en escenario estático,
BlockAll, sin simulación física del propio entorno. No usarla para cuerpos móviles.
Nanite queda desactivado hasta verificar colisión fallback; los candidatos se marcan
en manifest. HLOD visual no debe retirar colisión de celdas recorridas. Aún falta
probar cooking, barridos de cápsula/rueda, suelo, portales, escalones y streaming
con Pawn real. Configurar colisión en código no demuestra recorrido jugable.

El contrato geográfico permanece X este, Y sur, Z arriba, cm; EGM2008 no es altura
elipsoidal. GeoReferencing del engine no se configura para convertir silenciosamente
Z. Se guarda el origen para transformación explícita futura. World origin rebasing
no se necesita en este piloto 2 km; evaluar LWC/origen local antes de expandir.

Escalabilidad: exportación por sistema/celda, presupuestos de triángulos y límites de
bounds; fachadas simplificables con la opción graybox (sin alterar huellas). Puntos
PCG conservan dimensiones/clase/procedencia. Edificios de huellas únicas no se
instancian como si fueran iguales. Prototipos de cubo unitario para representación
HISM distante se exportan en plan de instancing, con transforms/IDs y volúmenes
aproximados; no reemplazan la geometría fiel ni la colisión cercana.
