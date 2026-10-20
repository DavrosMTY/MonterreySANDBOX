## Problema y resultado

GEO-001, GEO-002 y GEO-003 / WORLD-001 sólo existían en el entorno local. Esta rama
incorpora el pipeline GIS, ciudad procedural, refinamiento del terreno y perfiles
viales, proyecto UE5.6, pruebas, documentación y manifests al repositorio principal.

Se conservan el commit inicial y los entregables locales. Los inputs del piloto
publicados tienen licencia revisada y avisos Copernicus/ODbL. Los modelos, escenas,+renders y ZIP se generan como assets de una prerelease, sin usar LFS ni cuotas de
almacenamiento de Actions. El README describe arquitectura, reproducción y límites.

## Validación y límites

La entrega GEO-003 local pasó 72 pruebas y la lectura de GLB/407 OBJ, incluida una
copia extraída del ZIP. Hay 1.136 edificios, 2.665 tramos y 1.077.198 triángulos.
Se conservaron origen, escala, grafo y fuentes. Las nuevas comprobaciones GitHub
se ejecutan en CI y dejan su resultado en el job summary.

Persisten 97 candidatos motorizados excluidos, cruces incompletos y un tramo cuya
superficie exportada llega a 15,52 %. Las correcciones de elevación son procedurales.
Unreal/Windows no se compiló ni ejecutó; no se certifica mundo totalmente conducible.

Este PR requiere revisión y **no debe fusionarse automáticamente**. Los artefactos
reconstruidos en GitHub se identifican por commit y hashes propios; no se presentan
como copias binarias idénticas de los ZIP históricos.
