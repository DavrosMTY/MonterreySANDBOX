# UE-001: proyecto nativo y ejecución automatizada

Motor fijado: **Unreal Engine 5.6.1**; asociación del descriptor 5.6. El runner
rechaza otro patch. El objetivo comercial es Windows PC. Linux es validación
nativa opcional, nunca una aprobación de Windows.

## Implementación

- Proyecto existente ampliado, sin sustituir GEO-001/002/003 ni sus entregables.
- Character C++ con cápsula 34/88 cm, caminar 400 cm/s, correr 650 cm/s, salto,
  cámara con spring arm y cuerpo provisional de BasicShapes del motor. Sin
  vehículos, tráfico, NPCs, mannequin comercial ni dependencia de StarterContent.
- HUD con controles WASD, mouse, Shift y espacio. Movimiento/input nativos,
  sin assets binarios de InputActions; no hay animación esquelética en este hito.
- GameMode exige PlayerStart marcado y suelo/espacio de cápsula comprobados;
  reintenta mientras carga colisión y no recurre a aparecer bajo la ciudad en (0,0,0).
- Importación completa de los 279 sectores por sistema: terreno estático excavado,
  edificios, calzadas, banquetas, puentes y túneles. Se conservan posiciones,
  EPSG:32614, EGM2008, 100 cm por metro de cuadrícula y pivotes locales.
- Los 2.673 nombres de piezas y sus IDs OSM se relacionan con cada sector.
  UMonterreySectorMetadata conserva JSON de procedencia en los meshes cocinados;
  la tabla de edificios pertenece al módulo runtime, no al plugin de editor.
- Sol, atmósfera, skylight dinámico, mapa, spawn y metadatos sólo se crean en UE.
  El mapa convertido usa World Partition y sectores; no se reconstruyen HLOD
  ni se habilita Nanite por asset sin verificar la colisión fallback.

## Estructura generada dentro del motor

`/Game/Maps/UE001_Centro` → `/Game/Maps/UE001_Centro_WP`.
Assets en `/Game/UE001/{Landscape,Roads,Sidewalks,Bridges,Tunnels,Buildings}`,
PCG/DataAssets auxiliares y actores externos de World Partition.

En Git sólo existen fuentes, descriptor y configuración de conversión. **Todavía
no existen .umap/.uasset generados por UE**. No se simulan con archivos vacíos.
El mapa de inicio configurado requiere completar la importación antes de abrir
el proyecto como juego. El cuerpo provisional no es un personaje AAA final.

## Automatización para agentes

El supervisor no ejecuta comandos ni instala herramientas. Estas entradas sirven
al agente y al runner autorizado:

```bash
# Recuperación no destructiva de los inputs ya publicados, con SHA256 fijo.
python tools/fetch_ue001_world.py --output artifacts/ue001-input-NUEVO
# Ejecución completa en un runner con UE_ROOT ya instalado/licenciado.
python tools/run_ue001.py --city artifacts/ue001-input-NUEVO/world --probes artifacts/ue001-input-NUEVO/traversal_probes.json --output artifacts/ue001-run-NUEVO
```

Sin UE, el segundo comando ejecuta tests/QA reales y deja A/B verificadas fuera del
motor y C/D/E bloqueadas con código 2. Cada ejecución requiere un directorio nuevo;
no reutiliza logs ni recibos históricos para aprobar niveles. Importar sobre un mapa
o carpeta de assets existente se rechaza. Para repetir una importación en un runner,
el agente usa una copia limpia del checkout y conserva primero los assets anteriores.
Nunca borra contenido del supervisor ni hace clean/reset del checkout para conseguirlo.

Con motor: compila Editor y Game, importa, convierte WP, carga el mapa, lanza un
proceso de juego, mide caminar/correr/cámara/suelo, captura PNG, cocina mediante
UAT BuildCookRun y lanza el binario empaquetado. Recibos con nonce por proceso,
hashes y logs nuevos. NullRHI, recibos obsoletos, mapa incorrecto, falta de movimiento
o captura ausente no aprueban D/E. El smoke es corto: no certifica todo el sector.

El workflow `ue001-unreal.yml` sólo admite dispatch confirmado a un runner
`self-hosted, Windows, X64, ue-5.6.1` ya autorizado. No instala el motor, no crea PR,
no sube artifacts/cache y no publica ejecutables automáticamente. Para aparecer en
la UI de dispatch de GitHub el workflow debe existir en la rama predeterminada tras
la revisión correspondiente; mientras tanto, el agente puede ejecutar el script
en el runner adjunto. No se dispara ahora: no hay runner autorizado disponible.

La publicación de fuentes usa un workflow separado, `ue001-release.yml`: runner
Ubuntu estándar público, 99 pruebas/QA reales, bloqueo C/D/E exigido, paquete con
hashes y prerelease inmutable. No descarga UE ni ejecuta el workflow de motor.
Permite publicar sin usar el canal de subida de la integración cloud, que devolvió
401 en uploads.github.com aunque Git/API/PR funcionaban. No se piden credenciales.

## Niveles de aprobación

| Nivel | Evidencia necesaria |
| --- | --- |
| A | Suite externa, hashes, OBJ/GLB, georreferencia, IDs y auditoría WORLD-001 |
| B | Estructura estática del proyecto, módulos/plugins, includes UHT y configuración; sin validar APIs de UE |
| C | Build real de los targets Editor y Game, UE5.6.1/UBT/UHT y logs de salida 0 |
| D | Importación y mapa WP cargado, proceso real con caminar/correr/cámara/suelo y PNG |
| E | Cooking/paquete y lanzamiento real de su binario con otro recibo y PNG |

A/B no implican C. Un mapa que carga sin prueba de movimiento deja D parcial.
Un paquete generado sin lanzarlo deja E parcial. El recibo mantiene flags separados
para Windows y Linux. Capturas Blender de hitos anteriores no cuentan como capturas UE.

Se mantienen las 97 vías motorizadas excluidas, cruces incompletos y alturas
procedurales del [diagnóstico GEO-003](../GEO003_DIAGNOSTICO.md). No se certifica
conducción ni accesibilidad peatonal global por preparar un Character.
