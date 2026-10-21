# INFRA-001 — infraestructura para ejecutar Monterrey Open World

Consulta: **21 de octubre de 2026, America/Mexico_City**. USD, antes de impuestos,
sin descuentos, créditos, reservas ni Spot. El usuario confirmó que no dispone de
una estación Windows/GPU: la recomendación parte de cloud.

**Recomiendo una VM AWS g4dn.2xlarge con Windows Server, GPU T4 de 16 GB y 400 GiB
gp3, controlada desde GitHub y apagada entre trabajos.** Es la mejor combinación
observada de costo, VRAM y APIs para delegar operaciones. Para comenzar deben
resolverse los derechos de acceso gráfico Windows y el acceso legal a UE5.6.1;
no se presupuestan como si estuvieran confirmados o fueran gratuitos.

La PoC propuesta tiene **máximo seis horas de cómputo y un presupuesto de US$50**,
incluyendo el primer mes de disco. Es una propuesta pendiente de autorización y
licencias, no una contratación ni garantía de completar la compilación al primer intento.

## Estado real y alcance de la investigación

UE-001 permanece en [PR #2](https://github.com/DavrosMTY/MonterreySANDBOX/pull/2),
sin fusionar. Su commit reproducible es
[`82464719ac658f3a7932c94ee791ea43c2a90b06`](https://github.com/DavrosMTY/MonterreySANDBOX/tree/82464719ac658f3a7932c94ee791ea43c2a90b06).
A/B tienen validación externa/estática; C/D/E siguen sin ejecución Unreal.
INFRA-001 parte de development y sólo añade documentación e investigación.
No incorpora a escondidas los cambios de PR #2 ni lo fusiona.

Se consultaron tarifas oficiales, Azure Retail Prices y el CSV regional de AWS.
La red cloud bloqueó las páginas comerciales; runners **estándar gratuitos del
repositorio público** hicieron únicamente consultas HTTP y versionaron evidencias.
No se crearon cuentas, VM, redes, almacenamiento de pago ni runners GPU.
[Fuentes](FUENTES.md), [datos](research/sources.json) y [cálculo reproducible](cost-model.json).
Una tarifa pública no confirma stock, cuota de GPU o elegibilidad de la cuenta.

## Tres finalistas

La base incluye Windows publicado, disco persistente durante todo el mes modelo
(30 días/720 h) e IPv4 indicado. **No es un total cerrado:** excluye RDS CAL/SAL u
otros derechos gráficos no confirmados, licencias comerciales adicionales, backups,
transferencia sobre franquicia, servicios auxiliares, impuestos y consumo Codex/API.
Un valor de licencia desconocido no se convierte en cero.

| Alternativa | GPU / VRAM | CPU / RAM | Cómputo Windows por hora | Persistencia por mes | Base con 20 h | Base con 80 h |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **AWS g4dn.2xlarge**, us-east-1 | T4 / **16 GB** | 8 vCPU / 32 GiB | **US$1,12** | 400 GiB gp3: **US$32,00** | **US$54,50** | **US$122,00** |
| **Azure NV12ads A10 v5**, eastus | 1/3 A10 / **8 GB** | 12 vCPU / 110 GiB | **US$1,46** | 512 GiB P20 LRS: **US$73,22** | **US$106,02** | **US$193,62** |
| **Vagon Computer Flame** | A10G / **24 GB** | 8 cores anunciados / 32 GB | **US$2,27** anunciado | 425 GB: **US$42,99** | **US$88,39** | **US$224,59** |

AWS incluye IPv4 automático sólo mientras corre: US$0,005/h, US$0,10/0,40 para
20/80 h. Azure modela una IPv4 Standard reservada todo el mes: US$3,60, incluso
cuando se desasigna la VM. Vagon no desglosa un IPv4 adicional para este producto.
Los tamaños de disco difieren por los escalones comerciales, no por una comparación
implícita del precio por GB. Todas las horas de instalación, shaders y espera con
la VM encendida cuentan como cómputo; no sólo las horas con el editor abierto.

### AWS: opción recomendada para automatización

El catálogo vigente consultado identifica Windows a US$1,12, SKU
`7Q8SXFV7BACMK4YX`, operación `RunInstances:0002`, sin SQL y tenancy Shared.
**US$0,752 es otro medidor sin la licencia Windows completa**; no se usó en los
presupuestos. La VM dedicada al proyecto no es un Dedicated Host físico.

Tiene GPU Turing apta para el camino gráfico previsto, driver NVIDIA GRID/WDDM,
acceso administrativo automatizable, EC2 Start/Stop, SSM y OIDC. Requiere confirmar
cuota G/VT y capacidad regional. Usar Windows Server 2022 Desktop Experience y
driver específico; no confundir CUDA/TCC con una sesión gráfica DirectX utilizable.

El disco gp3 es persistente y factura al detener la VM. Sus 3.000 IOPS/125 MB/s
base evitan pagar un extra de IOPS para empezar. El NVMe local de 225 GB es
temporal: sólo puede alojar cachés reconstruibles. No se almacena ahí el proyecto.
Usar **Stop**, no prometer hibernación GPU; RAM y sesión se reconstruyen al arrancar.

Amazon DCV en EC2 no necesita licencia DCV independiente, pero **AWS documenta
RDS CAL para el acceso remoto a la GUI de Windows Server, cualquiera que sea el
protocolo**. Ni DCV gratis ni la tarifa Windows de EC2 demuestran esos derechos.
Confirmar CAL/SAL y su costo con el titular/proveedor antes de habilitar la GUI.
No utilizar las sesiones de administración como sustituto de una licencia de
estación de desarrollo, ni una cuenta automática para eludir requisitos.

### Azure: alternativa con más RAM y menos VRAM

La API devuelve US$1,46/h **Windows, Consumption, no Spot** en eastus; US$0,908 es
Linux o Dev/Test, no el precio empleado. En southcentralus el medidor Windows
consultado es US$1,642/h. La cercanía de Texas a Monterrey no implica menor precio
ni una latencia que ya se haya medido.

NV12 tiene 110 GiB RAM, pero **sólo 8 GB de los 24 GB físicos de la A10**. NV6
reduce a 4 GB, por lo que no es el ahorro recomendado para este piloto Lumen.
La extensión NVIDIA de Azure permite automatizar el driver GRID. Sus derechos
GRID y los de Windows/RDS/AVD son conceptos separados.

Se eligió P20 por capacidad de 512 GiB y rendimiento SSD predecible. Una variante
Standard SSD E20 cuesta US$38,40/mes: base **US$71,20 / US$158,80** para 20/80 h,
pero añade operaciones a US$0,002 por 10.000 y menor rendimiento. No se oculta
ese cambio como si fueran discos equivalentes. No se presupuestó bursting pagado.

Desasignar mediante ARM: apagar Windows dejando la VM **Stopped/Allocated** puede
seguir cobrando cómputo. El disco temporal D: no conserva datos con todas las
operaciones; usar managed disk para fuentes, UE y resultados. Windows 11/AVD
puede requerir derechos propios: no se asume incluido por la tarifa Server.

### Vagon: escritorio gestionado, autonomía aún parcial

La tarifa pública Flame es US$2,27/h, A10G de 24 GB y 32 GB RAM. El disco Personal
parte de 75 GB por US$7,99/mes; sumar 350 GB cuesta siete bloques de US$5:
425 GB = US$42,99/mes. Una PoC más ajustada con 275 GB sería US$27,99/mes, siempre
que la instalación real deje espacio suficiente; no se promete compilar UE fuente ahí.

El producto anuncia Windows persistente y software instalable; puede simplificar
el primer acceso por navegador. Hay que confirmar región, permisos de instalación
VS/SDK, edición y derechos Windows, versión UE disponible y condición comercial
final antes de pagar. Los precios varían con la región y se usa saldo prepago.

**No se ha confirmado una API pública para encender/apagar Vagon Computer.** La API
Streams consultada corresponde a otro producto y no justifica automatizar Computer.
Con la máquina encendida, un runner interno puede ejecutar los scripts; el control
del ciclo de vida podría seguir requiriendo el panel. Por eso no es la primera
opción para eliminar operaciones humanas cotidianas, aunque sea un finalista de
escritorio gestionado para la PoC. No se recurrirá a APIs privadas no documentadas.

## Transferencia, suspensión y costos que permanecen

| Servicio | Entrada/salida consultada | Apagado y conservación |
| --- | --- | --- |
| AWS | 100 GB/mes de salida gratuita **agregados en la cuenta**; después, US$0,09/GB en el primer tramo de pago de us-east-1 (hasta 10 TB de ese tramo). No se asume esa franquicia disponible si la cuenta ya la consume. | Stop libera el cómputo; gp3/snapshots siguen cobrando. IPv4 automática se libera; Elastic IP retenida también cobra. |
| Azure | Entrada normal sin cargo; salida desde Norteamérica: primeros 100 GB/mes gratis, siguiente tramo US$0,087/GB en red Microsoft Premium. Transferencia entre regiones tiene otra tarifa. | Deallocate detiene cómputo; managed disks e IPv4 Standard retenida siguen cobrando. |
| Vagon | Entrada sin cargo; primeros 10 GB/mes de salida sin cargo, luego US$1,50 por cada 10 GB adicionales anunciados. | El disco/subscripción conserva software y datos y sigue facturando al apagar. |

20 Mbps sostenidos equivalen aproximadamente a **9 GB/h**: 20/80 h de streaming
son 180/720 GB, antes de artefactos. En Azure serían aproximadamente US$6,96/53,94
adicionales si quedaran disponibles los primeros 100 GB. En Vagon serían
US$25,50/106,50 sobre su franquicia de 10 GB. En AWS serían US$7,20/55,80
con su primer tramo de US$0,09/GB y los 100 GB disponibles.
Estas cifras son un escenario de bitrate, no una medición de DCV/Parsec.

Para el desarrollo delegado se recomienda **no transmitir video continuamente**:
el motor renderiza en la VM y Codex recibe logs, capturas PNG y resultados. Se
reserva una sesión visual breve para diagnóstico. La estimación principal supone
salida pequeña, no 80 horas de escritorio transmitido.

Backups, almacenamiento de objetos, secretos, imágenes y registros se presupuestan
por separado. No crear NAT Gateway, balanceador, AD administrado ni Bastion de pago
por defecto; podrían costar más que la GPU durante un uso de 20 horas. Si una vía de
licencias exige AD o servicios adicionales, debe cotizarse y aprobarse antes.

## Otras alternativas evaluadas

| Alternativa | Hallazgo y motivo de no elegirla como principal |
| --- | --- |
| Estación propia | Descartada para esta decisión: el usuario confirmó que no tiene una disponible. No se inventa costo cero ni se propone comprar hardware sin cotización. |
| AWS g5.2xlarge | A10G 24 GB, 8 vCPU/32 GiB, Windows US$1,58/h verificado; misma persistencia: base US$63,70/158,80 a 20/80 h. Mejora de VRAM si T4 no alcanza; no se crea automáticamente. |
| AWS g4dn.4xlarge | T4 16 GB, 16 vCPU/64 GiB, Windows US$1,94/h verificado; base US$70,90/187,60. Alternativa si falta RAM/CPU. Requiere nueva decisión de tamaño y cuota. |
| AirGPU | La página principal anuncia A10G, 8 vCPU/32 GB a US$1,05/h; 400 GB de SSD a US$28/mes, base anunciada US$49/112 para 20/80 h, antes de extras. Las antiguas URLs /pricing y /faq devolvieron 404; se usó la principal. Faltan confirmaciones de API de ciclo de vida, edición/derechos Windows, VRAM efectivamente asignada y tarifa de salida. No se presenta como oferta cerrada más barata. |
| Paperspace | Precio público A4000 US$0,76/h y oferta Linux/Windows; no se verificó una combinación actual concreta de A4000 + imagen Windows + almacenamiento suficiente + derechos gráficos. Los escritorios Windows explícitos incluyen GPUs más antiguas. No trasladar un precio de cómputo genérico a un escritorio UE confirmado. |
| RunPod / Lambda | Las ofertas GPU consultadas se orientan a entornos Linux/CUDA; no se verificó una imagen Windows gráfica licenciada para esta misión. Mucha VRAM de entrenamiento no sustituye un escritorio DX12. |
| Vultr / Shadow | Las URLs consultadas devolvieron 403/404; no se inventan tarifas ni disponibilidad actuales. |
| VM física/Dedicated Host | Posible con cotización y derechos de SO adecuados, pero no se verificó un precio que mejore el uso ocasional. No es requisito para este piloto. |

## Decisión y siguiente paso

Aprobar primero la [PoC limitada](POC.md) y sus condiciones, no una VM permanente
ni un contrato anual. La [arquitectura](ARQUITECTURA.md) separa repositorio público,
control privado, identidades temporales y sesión gráfica. Con presupuesto autorizado,
cuota y licencias resueltas, Codex puede automatizar la preparación y ejecutar C–E.
Si la licencia gráfica o el acceso a UE no pueden confirmarse dentro del presupuesto,
la decisión es **no arrancar el cómputo pagado** y traer una cotización corregida.
