# Recibo de sincronización GitHub

Repositorio principal: [DavrosMTY/MonterreySANDBOX](https://github.com/DavrosMTY/MonterreySANDBOX).
[PR #1: development → main](https://github.com/DavrosMTY/MonterreySANDBOX/pull/1),
abierto mediante la integración directa autenticada y sin fusionar.
Se conserva la restricción de Actions para crear/aprobar PR; el job de creación
se retiró del workflow. No se modificó la configuración de permisos del repositorio.

## Código e historial

`development` parte de `8015d293b945086e4e254d1ba52b3cba690c96f0`, el main original.
El commit inicial, la rama local work y todos los archivos previos se conservan.
Se verificó una copia recuperable adicional de 3.714 archivos contra sus SHA256,
más un bundle del historial y un archivo completo fuera del checkout. Sin reset,
force-push, borrado de entregables ni commits directos a main.

Commits de incorporación:

| Commit | Contenido |
| --- | --- |
| [9232c20](https://github.com/DavrosMTY/MonterreySANDBOX/commit/9232c205c88891513304eeb7dea9b8aa80082893) | GEO-001 y piloto con licencias revisadas |
| [9322ed0](https://github.com/DavrosMTY/MonterreySANDBOX/commit/9322ed05635a6debd94e59867dba1eb42478e5d9) | GEO-002 e integración UE preparada |
| [577b691](https://github.com/DavrosMTY/MonterreySANDBOX/commit/577b691d039019e4eed613e4f28c55f5e8632e6d) | GEO-003 / WORLD-001 y capas reversibles |
| [f39023e](https://github.com/DavrosMTY/MonterreySANDBOX/commit/f39023edf33e02d1d2a83497b5853f777cce1d13) | README, publicación, CI y política GitHub |
| [3f5c050](https://github.com/DavrosMTY/MonterreySANDBOX/commit/3f5c050a07c622262ad4f54a66c8063e733b9a20) | Hashes portables a Windows y Blender 4.3.2 fijado |

El commit que incorpora este recibo añade la verificación de descargas y retira
la creación de PR desde Actions conforme a la decisión del propietario.

## Entregables descargables

[Release GEO-003 / WORLD-001](https://github.com/DavrosMTY/MonterreySANDBOX/releases/tag/geo003-world001-3f5c050a07c6),
prerelease reconstruida desde el commit `3f5c050a07c622262ad4f54a66c8063e733b9a20`.
11 assets, 177.450.136 bytes en conjunto:

- ZIP GEO-001 piloto, GEO-002 y GEO-003 / WORLD-001.
- Modelo GLB, escena Blender y tres renders PNG reales.
- Avisos legales, manifest de procedencia/QA y SHA256SUMS.

Se descargaron los 11 assets, se verificaron los hashes de los nueve contenidos
contra el manifest y SHA256SUMS, y los tres ZIP superaron su CRC completo.
Acceso anónimo comprobado para cada asset. El [recibo estructurado](../manifests/github-release-verification.json)
registra todos los tamaños, hashes y enlaces, incluidos los dos archivos de control.
Las reconstrucciones no sustituyen los ZIP históricos y tienen hashes propios.

LFS no se activó porque su cuota de cuenta no está verificada. Se usaron Releases
tras comprobar límites oficiales: 1.000 assets por Release y cada archivo <2 GiB;
sin límite total documentado. Sin cachés ni uploads de artifacts de Actions.
No se subieron dependencias instaladas, temporales ni datos sin licencia revisada.

## Verificaciones

- [CI Linux y Windows](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39508590334): aprobado; 77 pruebas y pipeline sintético por sistema.
- [Reconstrucción real y publicación](https://github.com/DavrosMTY/MonterreySANDBOX/actions/runs/39508590342/job/118923667831): aprobado; 77 pruebas por hito, QA GLB/OBJ/geográfico, renders Cycles CPU con Blender 4.3.2 verificado por checksum.
- Clon limpio desde GitHub: 77 pruebas aprobadas y comprobación de publicación.
- Los 110 archivos del commit de la Release se descargaron públicamente y se contrastaron con sus objetos Git.
- El PR requiere revisión humana; no hay fusión automática.

El job histórico de PR del mismo workflow fue rechazado por la política de Actions;
no se cuenta como PR creado. El PR #1 fue creado posteriormente mediante API directa.

Unreal/Windows sigue sin compilar ni ejecutar. El piloto mantiene 97 candidatos
motorizados excluidos y las limitaciones de [GEO-003](GEO003_DIAGNOSTICO.md).
Las pruebas offline no certifican conducción, colisión ni streaming en motor.
