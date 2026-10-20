# GitHub como repositorio principal

Repositorio: https://github.com/DavrosMTY/MonterreySANDBOX.
`main` es la base revisada; la incorporación inicial usa `development`, creada
sobre el HEAD actual de main sin reescribirlo. Los siguientes avances se realizan
en ramas de trabajo con commits y Pull Requests. No se fusionan automáticamente.

Antes de sincronizar se conservaron los archivos locales y se verificó un bundle
del historial. El checkout y sus entregables históricos permanecen en el entorno.
La copia adicional está fuera del repositorio; no se publica ni se suben dependencias.
Los commits de incorporación organizan el estado actual por componentes/hitos;
no pretenden inventar un historial previo que no existía en Git.

## Contenido versionado

Código GIS y procedural, proyecto/configuración UE5.6, automatización, pruebas,
documentación, manifests y un piloto pequeño con licencias revisadas. Los inputs
permitidos se enumeran con hashes en `manifests/pilot-inputs.json`.
`tools/check_publication.py` verifica el conjunto exacto indexado en Git.

El código no incluye una licencia general nueva de redistribución. Las bases
geográficas tienen condiciones separadas; consultar DATA_LICENSES.md. No se
redistribuyen archivos de Unreal Engine ni assets comerciales de terceros.

## Cuotas, tamaños y artefactos

Visibilidad pública comprobada mediante respuesta web anónima y metadato
`octolytics-dimension-repository_public=true`, 20 de octubre de 2026.
Se revisó documentación oficial de GitHub:

- Runners estándar para repositorios públicos: gratuitos. Se usan ubuntu-latest
  y windows-latest; no larger runners, imágenes personalizadas o servicios de pago.
- Releases: hasta 1.000 assets, cada archivo menor de 2 GiB. La documentación no
  impone límite total de almacenamiento ni ancho de banda de Releases.
- LFS está instalado (3.6.1), pero la cuota de cuenta no se pudo consultar por el
  bloqueo API. No se activan filtros/punteros LFS ni se suben objetos LFS.
- Caché persistente de Actions desactivada. `upload-artifact` no se ejecuta en push
  o PR: sólo se permite en un dispatch que confirme una comprobación de cuota.
  No se ha confirmado la cuota de almacenamiento de cuenta; no se usa.

Fuentes oficiales y hashes de consulta: `manifests/github-storage-policy.json`.
Los inputs licenciados del piloto son pequeños; los modelos grandes, escenas,
renders y ZIP están ignorados en Git y se publican como Release assets.

## Automatización inicial

`.github/workflows/bootstrap-sync.yml` se activa una vez al incorporar el marcador
`.github/publication/bootstrap.json` en development. Sólo opera en este repositorio
público. Sus jobs independientes intentan abrir el PR development → main y reconstruir
los entregables desde los inputs versionados, ejecutar QA, renderizar en Blender y
publicar una prerelease asociada al commit exacto. No fusiona el PR.

Nombre de tag: `geo003-world001-<primeros 12 caracteres del commit>`.
El publicador rechaza reemplazar Releases existentes o sobrescribir assets. Cada
asset tiene tamaño/hash en release-manifest.json y SHA256SUMS.txt. Las nuevas
reconstrucciones no se presentan como ZIP idénticos a los históricos locales.

El README describe los resultados locales. Los recibos de la Release describen
las pruebas, versiones y hashes del runner GitHub. Unreal no se instala ni ejecuta;
los recibos permanecen explícitos sobre ese bloqueo.

## Permisos y bloqueos diagnosticados

Git HTTPS funciona mediante la autenticación de plataforma. La ruta API desde el
entorno cloud devolvió CONNECT 403 del proxy; no es evidencia de token inválido.
Se conservaron las credenciales existentes. api.github.com y uploads.github.com
se añadieron al borrador de red, sin afirmar que guardar lo active en runtime.

La automatización remota usa el GITHUB_TOKEN acotado de Actions, con contents:write
para Release y pull-requests:write para PR. GitHub puede bloquear la creación de
PR por una política del repositorio. En ese caso el job summary identifica el
ajuste necesario: Settings → Actions → General → Allow GitHub Actions to create
and approve pull requests. Ese permiso no autoriza fusiones; el flujo no las ejecuta.
La publicación de workflows mediante Git también requiere el permiso Workflows
write de la integración si GitHub lo restringe; se informa cualquier rechazo real.

No se publican secretos ni se solicitan tokens en el chat. Un bloqueo se reporta
con la operación y el permiso exacto; los pasos independientes continúan.
