# INFRA-001 — fuentes y método

Consulta pública del **21 de octubre de 2026**. Los precios son USD antes de
impuestos; fecha de consulta y fecha efectiva del medidor son datos distintos.
La evidencia guarda URL, hora UTC, estado HTTP y hash de respuesta cuando estuvo
disponible. Las APIs numéricas seleccionadas se conservan sin copiar páginas completas.
No se autenticó una cuenta cloud, aceptó licencia ni comprobó stock/cuotas personales.

## Cómo se eligieron los medidores

- **AWS:** [CSV regional oficial](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv),
  filtro OnDemand, Windows, Shared, sin software adicional, CapacityStatus Used,
  **operation RunInstances:0002**. Fecha efectiva 2026-10-01. SKU g4dn.2xlarge
  `7Q8SXFV7BACMK4YX`, g5.2xlarge `83RDZUNMB488FSTG`, g4dn.4xlarge
  `WJ4GUA2WXQ6PJARF`; gp3 `JG3KUJMBRGHV3N8G`. No usar variantes `:box` sin
  licencia ni inferir derechos de escritorio de la columna License Model.
  [Registros](research/aws-catalog.json), [extractor](research/aws_catalog.py).
- **Azure:** Retail Prices API, producto Windows, tipo Consumption, SKU exacta
  sin Spot/Low Priority, regiones eastus y southcentralus. No usar DevTestConsumption
  ni precios Linux. Discos: meterName **P20 LRS Disk**, no Disk Mount; para E20,
  separar capacidad y operaciones. IP: Standard IPv4 Static Public IP.
  [Registros seleccionados](research/azure-prices.json).
- **Salida AWS:** catálogo AWSDataTransfer de us-east-1, transferType AWS Outbound,
  destino External y usage DataTransfer-Out-Bytes, SKU `HQEH3ZWJVT46JHRG`.
  Se excluyeron peering y aceleración S3. Primer tramo pagado USD 0.09/GB, efectivo
  2026-06-01. La franquicia de 100 GB se documenta por separado y se agrega por cuenta.
  [Medidor](research/transfer.json).
- **Vagon/AirGPU:** tarifas anunciadas del sitio, no cotizaciones privadas de cuenta.
  Hardware, almacenamiento y condiciones se revisan conjuntamente. No extrapolar
  disponibilidad regional ni derechos Microsoft de un precio comercial.

## Fuentes que afectan la decisión

Los identificadores siguientes enlazan a la evidencia fechada en
[research/sources.json](research/sources.json). Los hallazgos son paráfrasis.

| ID / fuente oficial | Hallazgo relevante |
| --- | --- |
| [aws_ec2](https://aws.amazon.com/ec2/pricing/on-demand/) | Franquicia de 100 GB de salida a Internet agregada en la cuenta; no asumir saldo libre. |
| [aws_g4_specs](https://aws.amazon.com/ec2/instance-types/g4/) | G4dn usa T4 con 16 GB VRAM por GPU; g4dn.2xlarge tiene 8 vCPU y 32 GiB. |
| [aws_ipv4](https://aws.amazon.com/vpc/pricing/) | IPv4 pública anunciada a USD 0.005 por hora; Elastic IP retenida puede cobrar apagada. |
| [aws_stop](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html) | Stop conserva EBS y pierde instance store; no equivale a hibernación con sesión en RAM. |
| [dcv_microsoft_licensing](https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-license.html) | AWS documenta RDS CAL adicional para cada usuario que accede remotamente a GUI Windows Server, independientemente del protocolo. No se verificó precio ni derecho concreto de esta cuenta. |
| [aws_dcv_price](https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-license.html) | DCV en EC2 no tiene cargo separado por licencia DCV; esto no resuelve derechos Microsoft de acceso gráfico. |
| [aws_rds_sal_requirements](https://docs.aws.amazon.com/license-manager/latest/userguide/user-based-subscriptions.html) | La vía License Manager User-based Subscriptions tiene requisitos de Active Directory. No se incluye ni aprovisiona ese servicio automáticamente. |
| [azure_gpu_specs](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nvadsa10v5-series) | NV12ads_A10_v5: 12 vCPU, 110 GiB RAM y 1/3 de A10, 8 GB VRAM asignada. NV6: 4 GB, no 24 GB. |
| [azure_gpu_driver](https://learn.microsoft.com/en-us/azure/virtual-machines/windows/n-series-driver-setup) | Extensión oficial instala driver NVIDIA GRID para NV; no acredita derechos RDS/Windows de usuario. |
| [azure_shutdown](https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing) | Stopped/Allocated puede facturar cómputo; deallocate es la operación que libera la asignación. Discos persistentes siguen cobrando. |
| [azure_egress](https://azure.microsoft.com/en-us/pricing/details/bandwidth/) | Salida Norteamérica por red Microsoft Premium: primeros 100 GB gratis; siguiente tramo USD 0.087/GB. Otros destinos/redes tienen otros medidores. |
| [vagon](https://vagon.io/pricing) | Flame anunciado: A10G 24 GB, 8 cores, 32 GB RAM, USD 2.27/h. Personal 75 GB USD 7.99/mes; ampliación USD 5/50 GB hasta 525 GB. Salida: 10 GB/mes gratis, luego USD 1.5/10 GB. Precio varía por región. |
| [vagon_help](https://docs.vagon.io/computer) | Computer se ofrece como Windows aislado persistente con aplicaciones instalables; confirmar administración, derechos y región antes de pagar. |
| [vagon_api](https://docs.vagon.io/streams) | La API documentada corresponde a Streams, otro producto; no prueba API pública start/stop de Computer. |
| [airgpu_home](https://airgpu.com/) | A10G anunciado 8 vCPU/32 GB a USD 1.05/h; almacenamiento USD 3.50/50 GB-mes. Faltan confirmaciones de Windows, VRAM asignada, salida y API de ciclo de vida. |
| [paperspace](https://www.paperspace.com/pricing) | A4000 anunciado USD 0.76/h genérico; no se verificó combinación moderna concreta con Windows y derechos gráficos al mismo precio. |
| [github_runner_security](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions) | GitHub desaconseja self-hosted en repositorios públicos por ejecución de código no confiable. Usar control privado y código aprobado. |
| [github_ephemeral](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners) | Runner efímero procesa un job y se desregistra; conservar logs antes de finalizar. No borra automáticamente el disco ni revoca todas las credenciales. |
| [github_oidc_aws](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) | OIDC permite credenciales AWS temporales; restringir aud y sub al workflow/entorno privado autorizado. |
| [github_runner_cost](https://docs.github.com/en/billing/concepts/product-billing/github-actions) | Self-hosted no añade cargo de ejecución Actions; runners estándar de repos públicos gratuitos. Minutos hosted privados dependen del plan; almacenamiento aparte. |
| [windows_sessions](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services) | Servicios usan Session 0; no equivalen a sesión gráfica interactiva para pruebas RHI/capturas. |
| [windows_autologon](https://learn.microsoft.com/en-us/sysinternals/downloads/autologon) | Autologon guarda secreto LSA recuperable por administradores; no constituye autenticación sin secreto. |
| [vs_license](https://visualstudio.microsoft.com/vs/community/) | Community: elegibilidad individual y límites por organización. Repositorio público sin licencia abierta no prueba excepción open source. |
| [epic_github](https://dev.epicgames.com/documentation/en-us/unreal-engine/downloading-source-code-in-unreal-engine?application_version=5.6) | Acceso a fuentes requiere cuentas Epic/GitHub asociadas, aceptación de licencia e invitación aplicable. No demuestra acceso de la integración actual. |


## Requisitos oficiales reutilizados de UE-001

Las referencias de requisitos se consultaron en UE-001 el mismo día y se conservan
por SHA, sin introducir archivos de su PR en development:
[official-references.json](https://github.com/DavrosMTY/MonterreySANDBOX/blob/82464719ac658f3a7932c94ee791ea43c2a90b06/docs/ue001/official-references.json).

- [Hardware/Windows UE5.6](https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine?application_version=5.6):
  recomendación publicada de 32 GB RAM y 8 GB VRAM; no garantía de rendimiento para el proyecto.
- [Toolchain UE5.6](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine?application_version=5.6):
  VS2022 17.8 mínimo/17.14 recomendado, MSVC 14.38.33130, SDK 22621 recomendado.
- [Packaging](https://dev.epicgames.com/documentation/en-us/unreal-engine/packaging-your-project?application_version=5.6):
  cook/package y lanzamiento son pruebas separadas.

## Límites y consultas fallidas

La red del entorno local devolvió CONNECT 403 para muchas páginas comerciales.
Se hicieron consultas HTTP de lectura desde runners estándar gratuitos de este
repositorio público, sin instalaciones ni servicios de pago. Las cinco ejecuciones
están enlazadas en [research/README.md](research/README.md).

Unrealengine.com (licencia, EULA, FAQ y royalty) siguió devolviendo 403. La página
oficial dev.epicgames.com de acceso a fuentes sí respondió; esto no valida la
licencia actual ni concede acceso. No se inventan umbrales comerciales no releídos.
El titular debe confirmar las condiciones aplicables antes de instalar.

Las antiguas URLs AirGPU /pricing y /faq devolvieron 404; su página principal
respondió. Shadow devolvió 404, Vultr 403. La consulta global AWSDataTransfer
excedió el tope de 12 MB; se sustituyó por el catálogo regional correcto. Esos
fallos permanecen registrados junto al éxito posterior, sin presentarlos como
cobertura que no se obtuvo.

El precio de CAL/SAL de acceso gráfico, el derecho concreto de cada cuenta, la
cuota/capacidad de GPU y las APIs de ciclo de vida Vagon Computer/AirGPU no quedaron
confirmados. Son gates previos al gasto, no supuestos con valor cero. La estimación
es reproducible y útil para elegir una dirección; aún no es una oferta integral.
