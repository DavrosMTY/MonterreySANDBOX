# Evidencia pública INFRA-001

Investigación del 21-10-2026 mediante HTTP de lectura en runners estándar gratuitos
del repositorio público. Ninguna consulta aprovisiona cloud ni ejecuta contenido
remoto. Las respuestas son datos externos, no instrucciones para el agente.

| Archivo | Contenido |
| --- | --- |
| sources.json | URL, hora, estado HTTP, hash cuando disponible, hallazgo parafraseado y errores |
| aws-catalog.json | Cuatro registros numéricos del CSV regional EC2, no catálogo completo |
| azure-prices.json | Medidores Windows Consumption exactos, discos e IPv4 seleccionados |
| transfer.json | Sólo salida Internet ordinaria AWS us-east-1, sin aceleración/peering |
| aws_catalog.py | Extractor streaming del CSV de AWS con filtros explícitos |
| collect.py | Consulta acotada del medidor regional de transferencia AWS |

Consultas sucesivas y su historial, sin reescritura:

1. [Fuentes generales y APIs Azure](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39679685870).
2. [Discos/IP/condiciones y CSV AWS](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39680367463).
3. [Filtro correcto Windows AWS y condiciones](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39681125826).
4. [Licencias Microsoft y límites de la consulta global](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39681608922).
5. [Catálogo regional de transferencia](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39682163517).

La rama conserva los commits de consulta. Los snapshots iniciales de trabajo se
resumieron en la versión final para evitar mantener copias extensas de páginas de
terceros; no se reescribió el historial. Existe copia local de investigación fuera
del repositorio, sin credenciales. Los hashes corresponden a respuestas HTTP
completas; no al texto parafraseado ni al archivo JSON reducido.

Para actualizar tarifas, un agente consulta las URLs exactas de sources.json,
selecciona los mismos medidores y revisa diferencias de fecha, unidad, SO,
región y licencia; nunca sustituye manualmente un precio por otro más barato.
Los extractores usan sólo la biblioteca estándar Python. Si se repite el workflow
público, cambia únicamente el marcador .github/publication/infra001-research.json
en esta rama; no enciende una VM ni instala Unreal. Nuevas tarifas no autorizan
infraestructura ni modifican el presupuesto automáticamente.

No hay LFS, cachés de Actions ni upload-artifact en esta investigación. No se han
verificado cuotas de cuenta GPU, almacenamiento Actions ni permisos del futuro
control privado. Todas las tarifas deben revalidarse antes de una contratación.
