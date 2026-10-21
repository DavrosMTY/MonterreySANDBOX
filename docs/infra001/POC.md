# INFRA-001 — prueba de concepto limitada, pendiente de autorización

Objetivo: obtener evidencia real de C (compilación), D (mapa y personaje) y E
(ejecutable Windows lanzado) con el mínimo gasto razonable. No se ha contratado
infraestructura, instalado UE ni ejecutado el motor durante INFRA-001.

## Presupuesto propuesto y condiciones previas

AWS us-east-1, g4dn.2xlarge Windows, T4 16 GB, 8 vCPU/32 GiB y 400 GiB gp3.
Máximo **seis horas acumuladas encendida** y **US$50 antes de impuestos**, sin
créditos, Spot ni compromiso mensual de cómputo. No está autorizado todavía.

| Partida | Cálculo | USD |
| --- | --- | ---: |
| VM Windows | 6 × 1,12 | 6,72 |
| Primer mes completo gp3 | 400 × 0,08 | 32,00 |
| IPv4 automática durante cómputo | 6 × 0,005 | 0,03 |
| Base conocida | | **38,75** |
| Reserva hasta 50 | Licencias confirmadas, pequeños outputs privados y transferencia/secretos/control | **11,25** |

El disco se prorratea por uso real, pero se reserva el mes entero para no ocultar
lo que cuesta conservar UE y el proyecto apagados. No incluir snapshots o un
segundo disco sin desglosarlos. No se promete que la reserva cubra CAL/SAL: su
precio y elegibilidad no se han confirmado. Si no cabe legalmente en US$50,
**detener la planificación pagada y presentar nueva cotización antes de arrancar**.
No agregar AD administrado, NAT, Bastion o Marketplace de pago para intentar encajar.

Gates previos a cualquier gasto:

- Autorización expresa del presupuesto, instalación considerable UE/VS/SDK y
  recursos concretos, con retención de disco de 30 días y revisión posterior.
- Cuenta cloud del titular con facturación/MFA y cuota On-Demand G/VT de al menos
  8 vCPU; comprobar capacidad regional. No se ha consultado cuota de una cuenta.
- Confirmación de derechos Windows Server para desarrollo y GUI, RDS CAL/SAL
  cuando corresponda, y su precio. La tarifa de SO y licencia DCV no los prueban.
- Acceso Epic autorizado a un **Installed Build UE5.6.1** y aceptación aplicable de
  licencia por el titular. La integración actual no puede leer EpicGames/UnrealEngine.
  No existe aquí un instalador UE Windows silencioso autenticado ya disponible.
- Elegibilidad Visual Studio Community o licencia adecuada. Repositorio público
  sin licencia abierta no basta para declarar la excepción open source.
- Autorizar acceso seleccionado al control privado, sesión gráfica de robot y
  guardián externo. Ninguna contraseña se solicita ni comparte en el chat.

La licencia vigente de Epic no pudo releerse en unrealengine.com (HTTP 403); no
se da por aceptada ni se inventan términos comerciales. Usar las páginas oficiales
y la aceptación del titular. Puede ser necesario un SSO/MFA inicial en canal oficial,
remoto asistido, sin que el usuario programe o opere Unreal Editor.

El instalador de Epic Games Launcher no equivale a tener UE5.6.1. Una imagen con
UE debe comprobar procedencia, licencia, precio y `Engine/Build/Build.version`.
Si sólo se consigue código fuente del motor, se detiene esta PoC antes de reservar
GPU: compilar el motor completo requiere otro presupuesto, tiempo y almacenamiento.
No publicar la instalación como artefacto para eludir las condiciones de Epic.

## Ejecución automatizada después de resolver los gates

Fuente inicial fijada: `82464719ac658f3a7932c94ee791ea43c2a90b06` (PR #2 abierto).
El operador será Codex mediante el controlador privado propuesto; estos pasos no
son comandos que deba ejecutar el supervisor.

| Etapa | Tiempo orientativo dentro de 6 h | Trabajo y evidencia de salida |
| --- | ---: | --- |
| Bootstrap | 1,5 h | Windows/driver WDDM, UE5.6.1 legal, VS2022/SDK, Python y dependencias fijadas; inventario con espacio libre y GPU/RHI |
| C | 1,5 h | UHT/UBT reales de Editor y Game, código de salida, logs y hashes de binarios |
| D | 1,5 h | Importación GEO-003 por celdas, WP, mapa cargado, colisiones y prueba del personaje; PNG auténtica y recibo de la misma ejecución |
| E | 1 h | UAT BuildCookRun Win64, ejecución del paquete, prueba y captura propias; hash/tamaño del distribuible |
| Evidencia y cierre | 0,5 h | Exportación, verificación de hashes, estado de etapas y Stop comprobado desde fuera de la VM |

Son límites de planificación, no tiempos medidos ni garantía de terminar. Descarga,
instalación, shader compilation, fallos y esperas con la VM encendida consumen la
misma bolsa. Cerca del límite se prioriza exportar evidencia y apagar; no ampliar
horas, máquina, disco o servicios automáticamente.

Toolchain propuesta: VS2022 17.14, MSVC 14.38.33130 y Windows SDK 10.0.22621.0,
con las versiones fijadas por UE-001; comprobar que siguen descargables legalmente.
Usar Windows Server Desktop Experience como host cloud: **no constituye certificación
de compatibilidad del juego en Windows 11 de consumidor**. Esa prueba queda para
un hito posterior.

Antes de gastar GPU, revisar por PR el controlador y el límite de espera visual:
UE-001 tiene 180 segundos de play timeout, posiblemente insuficientes con shaders
fríos. Separar calentamiento de RHI/shaders y medición de gameplay, fijando un
límite explícito dentro del presupuesto. No aceptar una pantalla negra como éxito.

Ejecutar `tools/run_ue001.py` una vez hasta la etapa viable con inputs verificados
y carpeta nueva. El flujo construye Editor/Game, importa con Python, convierte WP,
prueba juego y empaqueta. Si falla, preservar logs y workspace; corregir código en
rama/PR y usar nuevo checkout para otro intento autorizado. No reutilizar un proyecto
poblado para una importación que rechaza assets existentes. No sustituir geodatos por
fixtures para conseguir un resultado verde.

## Criterios de aprobación y recibos

| Nivel | Evidencia mínima | Estado al publicar INFRA-001 |
| --- | --- | --- |
| A: código/datos externos | Suite externa y QA, SHA de fuentes y entradas | UE-001 reportó satisfactorio; INFRA no lo convierte en prueba Unreal |
| B: estructura | Validación estática de proyecto/configuración/importador | Preparado en UE-001; no equivale a UHT/UBT |
| C: compilación nativa | UE5.6.1 exacto, UHT/UBT Editor+Game con éxito, logs y binarios | **Pendiente, motor no disponible** |
| D: mundo en motor | Importación real, mapa WP guardado/cargado, RHI GPU, caminar/correr/cámara/suelo y PNG de esa ejecución | **Pendiente** |
| E: ejecutable | Cooking/package Win64 más lanzamiento y prueba del binario empaquetado; nonce y PNG distintos de la sesión de editor | **Pendiente** |

El manifest del run debe relacionar SHA fuente, hashes de inputs, versión exacta
motor/toolchain/driver, instancia/región (sin secretos), mapa, nonce, hora UTC,
códigos de salida y hashes de logs/PNG/paquete. Conservar también fallos. No marcar
C por tener un `.uproject`, D por iniciar el proceso sin validar mapa/personaje,
ni E por tener un ZIP o por ejecutar solamente `UnrealEditor -game`.

La importación debe conservar EPSG:32614/EGM2008, 100 cm por metro UTM, IDs OSM,
procedencia y separación por sectores. El candidato tiene 279 celdas y 2673 partes
según UE-001; verificar conteos reales, no usar esas cifras como resultado de una
importación aún no realizada. Mantener exclusiones de 97 tramos motorizados y QA
de cruces incompletos. Caminar en un sector no certifica toda la ciudad recorrible.

## Intervención humana que queda

| Actividad | Frecuencia | Alternativa y límite |
| --- | --- | --- |
| Cuenta, pago, MFA y aceptación Epic/Microsoft | Inicial y cuando el proveedor la requiera | Titular en portal oficial; Codex prepara todo lo demás, sin recibir credenciales |
| Elegibilidad de licencias y presupuesto | Inicial/cambio de condiciones | Cotización aprobada; no puede decidirse una aceptación legal por el titular |
| Permisos GitHub App/OIDC y sesión automática | Inicial | Integración seleccionada, rol temporal y secreto de robot en vault; permisos mínimos |
| Código, importación, build, QA, captura y paquete | Cada cambio aprobado | Automatizable por scripts/runner; no requiere al usuario abrir Editor ni ejecutar comandos |
| Desbloqueos por MFA, falta de cuota/capacidad o fallos de GUI | Excepcional | Diagnóstico y correcciones automáticas cuando estén autorizadas; escalar sólo la decisión que requiera al titular |
| Valoración visual y prioridades del mundo | Por hito | Revisión de capturas/replays por el supervisor; Codex puede hacer QA geométrico y detectar regresiones, no suplir preferencias |

El proyecto no debe depender de una sesión del propietario conectada diariamente.
Si el proveedor fuerza panel manual en cada arranque, falla el objetivo de autonomía;
Vagon queda como alternativa de menor preparación, no como equivalente comprobado.

## Cierre seguro y siguiente decisión

Apagar VM, verificar estado detenido, exportar resultado y registrar horas acumuladas.
Detener no elimina el disco: con 400 GiB gp3 sigue costando aproximadamente US$32
por mes completo. Al día 30, revisar continuidad y respaldo antes de renovar o
eliminar únicamente recursos nuevos autorizados. No borrar trabajo existente.
Las alertas de presupuesto no garantizan un tope absoluto; se necesita el guardián
de tiempo y el bloqueo de nuevos arranques. Si no se aprueban estos gates, la PoC
permanece en diseño y se sigue trabajando en código/documentación verificable.
