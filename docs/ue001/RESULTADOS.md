# UE-001: resultados verificados

21 de octubre de 2026, America/Mexico_City.
Código validado: `4b5ec00ac50e30a39d158494716c2fbd9f028450`, checkout limpio.
[Recibo estructurado](VALIDATION.json). La incorporación posterior de este recibo
sólo documenta los resultados; no representa otra compilación.

| Nivel | Resultado real |
| --- | --- |
| A — externo | **Aprobado:** 99 tests, 0 fallos/errores/omitidos, preflight de 279 sectores/2.673 piezas y QA GLB/407 OBJ/geográfico |
| B — estructura | **Aprobado estático:** descriptor, módulos, plugins, configuración, límites editor/runtime y orden de includes UHT; sin ejecutar UHT ni validar APIs UE |
| C — compilación C++ | **Bloqueado:** UE5.6.1/UBT/UHT no disponibles; no se ejecutó una compilación |
| D — mapa y exploración UE | **Bloqueado:** no se importó ni cargó ningún mapa en UE, no hay captura UE |
| E — ejecutable | **Bloqueado:** no hay cooking, paquete ni ejecutable generado o probado |

Se ejecutó el pipeline completo hasta el bloqueo con salida 2 prevista. Los logs,
JUnit, plan de importación, candidatos de spawn y auditorías completas se conservan
en `artifacts/ue001-validation-001/` y en el paquete de fuentes/evidencia UE-001.

El QA real leyó 1.077.198 triángulos, 2.673 piezas GLB y los 407 OBJ (compatibilidad
y sectores). Error máximo de bounds OBJ del preflight: 0,000000005 cm. No se
cambió el origen, el datum ni la escala; se relacionaron todos los nombres/IDs.
El checksum de los 1.088 archivos GEO-002/GEO-003 retenidos antes de este hito sigue
idéntico. No se regeneraron ni sustituyeron sus modelos o renders.

Las 22 pruebas nuevas incluyen corrupción de hashes, ejes/unidades, transformaciones,
IDs/sectores, datum, coordenadas no finitas, modelo de probes incorrecto, escape ZIP,
no sobrescritura, versión de motor y recibos obsoletos/incompletos. No son pruebas
de ejecución C++ ni una emulación del motor. Las 77 pruebas previas también pasan.

Se conserva la aceptación offline con refinamiento pendiente de WORLD-001: 97 vías
motorizadas excluidas, 15 cruces incompletos y un tramo exportado de 15,52 %. Preparar
un Character no convierte el piloto en una ciudad peatonal o vial certificada.

## Entrega revisable

La rama `feature/ue001-first-playable` parte de development. El PR se dirige a
**development**, sin fusión automática ni cambios a la restricción de Actions.
La prerelease UE-001 distribuye **fuentes y evidencia, no un juego ejecutable**.
La Release GEO-003 y sus assets originales no se sobrescriben. No se sube Unreal,
DDC, dependencias, credenciales ni se activa LFS/almacenamiento de Actions.

## Siguiente paso que habilita C–E

Adjuntar o autorizar un runner Windows con UE5.6.1 instalado legalmente, VS2022/SDK,
GPU y una sesión capaz de renderizar. Propuesta: 8 vCPU, 64 GB RAM, GPU 8 GB y 200 GB
SSD libres. El detalle y las alternativas están en [infraestructura](INFRAESTRUCTURA.md).
No se contrató infraestructura ni se inició una instalación considerable.

Una vez disponible, el agente ejecuta el mismo pipeline y conserva nuevos logs,
recibos y capturas auténticas. Si C falla, corrige el C++ y recompila; si D falla,
no empaqueta un mapa sin validar. Sólo tras probar el binario se puede aprobar E.
