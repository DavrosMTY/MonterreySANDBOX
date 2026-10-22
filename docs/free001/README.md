# FREE-001 — explorador web gratuito de Monterrey

**Presupuesto activo: US$0.** No se autorizan AWS, Azure, Vagon, VM de pago,
pruebas con tarjeta ni servicios que generen cargos. Las propuestas INFRA-001
son históricas y no autorizan compras. Unreal Engine **5.6.1 / Windows PC** sigue
siendo el objetivo definitivo; este visor es una herramienta de visualización.

## Primera versión funcional

Three.js 0.180.0 / WebGL 2, aplicación estática sin backend, cuentas, mapas en vivo,
telemetría ni recursos de pago. Usa exclusivamente el GLB real GEO-003 / WORLD-001
publicado, hash `c07d1a91e37bea063c638cb51275a770ed0ab222c7a2b6c49f6a7dc30436bcfc`.
No genera ni sustituye la ciudad por una fixture. El piloto cubre 2 × 2 km y
conserva 1136 edificios, 2665 tramos OSM, puentes, banquetas y túneles del graybox.
Muchas alturas y correcciones son procedurales; no es una recreación visual final.

**[Abrir el explorador de Monterrey](https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/dd44f8e0a6eccf8be3362685a2ab847758fb38bb/index.html)** · [Prueba pública](public-verification.json)

Si el proveedor muestra «External Content Notice», pulsa **Open the page**. Ese
aviso inicial del servicio gratuito puede incluir publicidad; el visor no solicita
cuentas, contraseñas ni pagos y no incorpora anuncios propios. Se verificó el flujo
completo en Chromium, incluyendo ese paso. Es una vista temporal por CDN; **GitHub
Pages todavía no está habilitado** por el bloqueo de permisos.

[Descargar el sitio y los modelos optimizados desde GitHub](https://github.com/DavrosMTY/MonterreySANDBOX/archive/dd44f8e0a6eccf8be3362685a2ab847758fb38bb.zip).
No necesitas descargarlo para explorar: basta con abrir el enlace del visor.

## Controles

| Acción | Control |
| --- | --- |
| Avanzar / izquierda / retroceder / derecha | W / A / S / D |
| Mirar | Mantener botón derecho y arrastrar, o «Explorar la ciudad» para capturar mouse |
| Bajar / subir | Q / E |
| Acelerar | Shift |
| Soltar mouse | Esc |
| Vistas iniciales | Botones «Vista aérea» y «Nivel de calle» |
| Calidad / velocidad / atmósfera / malla | «Opciones gráficas» |
| Pantalla táctil | Arrastrar escenario para mirar; flechas en pantalla para desplazarse |

La cámara es libre; no hay personaje físico, vehículos, colisión continua con
paredes ni certificación de calles transitables. La vista de calle parte de un
punto de la línea fuente de Calle Ignacio Zaragoza. Un raycast ayuda a evitar
atravesar el suelo cargado; no es una simulación de peatón. Las limitaciones GEO-003,
97 tramos excluidos y cruces pendientes siguen vigentes.

## Calidad y carga progresiva

- **Baja:** radio de 310 m alrededor del punto explorado, resolución hasta 0,7×,
  sin sombras. Predeterminada en móvil y renderizadores por software detectados.
- **Equilibrada:** radio de 620 m, resolución hasta 1×, sin sombras.
- **Alta:** radio de 1500 m, resolución hasta 1,5× y sombras; puede cargar las 64
  celdas. Se reserva para equipos con capacidad suficiente.

Dos descargas concurrentes, prioridad por proximidad, cancelación de peticiones
obsoletas y liberación de geometría/materiales al salir del radio. Un sector
fallido queda visible como carga parcial y reintenta con espera de 15 segundos;
no se oculta con una malla falsa. Cada payload se verifica con SHA256 antes de
parsear el GLB. La geometría cercana es idéntica entre calidades.

El panel muestra FPS, triángulos dibujados, sectores residentes, estimación de
buffers de geometría y heap JS cuando el navegador lo expone. **No mide VRAM total**;
el heap puede tardar en bajar hasta que el navegador recolecte basura.

## Hosting gratuito y restricciones

GitHub Pages está disponible gratuitamente para repositorios públicos. Se revisaron
las páginas oficiales desde un runner estándar público: sitio publicado ≤1 GB,
ancho de banda con límite blando de 100 GB/mes y, para builds por rama, 10 builds/h.
La evidencia de fecha/hash vive en la rama `gh-pages`, `evidence/hosting.json`.
La aplicación no facilita transacciones ni ofrece un SaaS comercial: es un demo
técnico de validación. No se propone Pages como distribución comercial del juego.

Este sitio ocupa aproximadamente 14 MB con dependencias, metadatos y evidencia,
y el publicador impone un máximo propio de **50 MiB**. No añade modelos al branch
de desarrollo: los pequeños sectores comprimidos se publican sólo en `gh-pages`,
rama de hosting generada y separada. Se preserva su historial sin force push.
Con gzip determinista, sectores idénticos reutilizan los mismos objetos Git.

No se usa LFS, caché persistente ni almacenamiento de Actions Artifacts. Se usan
runners estándar del repositorio público, sin instalar otro navegador ni solicitar
una tarjeta. Los ZIP originales permanecen en la Release existente. No se toca
ningún ajuste que permita a Actions crear/aprobar PR.

La activación Pages por la integración y por GITHUB_TOKEN no quedó autorizada en
el primer intento: HTTP 403 al crear el sitio; no se afirma que Pages esté activo.
`evidence/pages.json` conserva el resultado exacto. Para habilitarlo se necesitan
los permisos que GitHub exige al crear Pages: **Pages: write y Administration: write**,
seleccionados sólo para este repositorio. No hacen falta contraseñas en el chat.

Se evalúa una vista temporal mediante rawgit.hack, un proxy/CDN público gratuito
sin cuenta, tarjeta ni recursos contratados. Sirve los mismos assets de GitHub por
un SHA de despliegue inmutable. No es GitHub Pages y no tiene SLA ni una cuota
numérica garantizada publicada; no se presenta como hosting comercial permanente.
Su URL ya pasó carga de GLB, controles, perfiles y vistas en un navegador real.
Los GLB .gz pueden redirigirse al mismo SHA en raw.githubusercontent.com; el test
permite sólo esa redirección estática de este proyecto, sin APIs ni servicios de pago.
Una vez autorizado Pages, se puede cambiar la URL sin alterar GIS, mallas ni Unreal.

## Pruebas y arquitectura

Ver [compatibilidad y automatización](ARQUITECTURA.md), [resultados](RESULTADOS.md),
[recibo geométrico](geometry-validation.json), y la [verificación pública](public-verification.json).
La comparación de FPS distingue software de GPU real y perfiles con distinta carga;
no se traslada a rendimiento de Unreal.
