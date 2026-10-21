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

`.github/workflows/bootstrap-sync.yml` se activa al cambiar el marcador
`.github/publication/bootstrap.json` en development. Sólo opera en este repositorio
público: reconstruye los entregables desde los inputs versionados, ejecuta QA,
renderiza en Blender y publica una prerelease asociada al commit exacto.
No crea ni aprueba PR. La apertura/reutilización del PR se realiza con el acceso
directo autenticado mediante `tools/publish_github.py pr`; nunca lo fusiona.

Nombre de tag: `geo003-world001-<primeros 12 caracteres del commit>`.
El publicador rechaza reemplazar Releases existentes o sobrescribir assets. Cada
asset tiene tamaño/hash en release-manifest.json y SHA256SUMS.txt. Las nuevas
reconstrucciones no se presentan como ZIP idénticos a los históricos locales.

El README describe los resultados locales. Los recibos de la Release describen
las pruebas, versiones y hashes del runner GitHub. Unreal no se instala ni ejecuta;
los recibos permanecen explícitos sobre ese bloqueo.

## Permisos y política de PR

Se verificó acceso Git HTTPS y acceso directo autenticado a la API de GitHub con
permisos de lectura y escritura. Se conservan las credenciales de plataforma;
no se publican secretos ni se solicitan tokens en el chat.

El intento inicial de PR mediante GITHUB_TOKEN fue rechazado por la política de
Actions. El propietario ha decidido mantener esa restricción. No se cambia el
ajuste “Allow GitHub Actions to create and approve pull requests”, y el workflow
de publicación ya no contiene un job de creación de PR. Las operaciones de PR usan
la integración directa autorizada; las Releases usan contents:write en Actions.

Si una operación futura se bloquea, se informa el permiso exacto y se continúa
con el trabajo independiente. No se sustituye un PR real por un enlace a un
formulario de comparación. No se fusiona ni reescribe main automáticamente.
