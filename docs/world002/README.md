# WORLD-002 — identidad visual sobre geografía real

Presupuesto US$0. Primera propuesta visual funcional en Three.js 0.180.0/WebGL2;
Unreal Engine 5.6.1 sigue siendo el destino del proyecto. No se ejecutó Unreal.

La rama parte de FREE-001 (`fab3b60e55d4f17c03e15f7acfe05744c9ca2c12`) y depende del
[PR #4](https://github.com/DavrosMTY/MonterreySANDBOX/pull/4), aún sin fusionar.
Los PR #1, #2 (UE-001) y #3 se conservan abiertos. No se mezcla infraestructura
pagada ni se modifica `GeoPipeline`, los inputs GIS o `Unreal`.

## Qué puedes explorar

- Comparar **Original · Graybox / Ciudad · WORLD-002** sin mover cámara ni sectores.
- Fachadas deterministas por identificador: pintura, ladrillo, concreto, ventanas,
  accesos, comercio, oficinas propuestas según etiqueta/altura, industria y techos.
- Asfalto, pavimento y banquetas; pintura condicionada por datos explícitos de OSM.
- Cruces, semáforos estáticos, señal ALTO, árboles y mobiliario; inventario y propuesta
  claramente separados en el sidecar. No se simula ni cambia tráfico.
- Día, atardecer, noche, sombras y atmósfera regulables.
- Fondo DEM georreferenciado de ±18 km, sin expandir la zona jugable de 2 × 2 km.
- Calidad baja/equilibrada/alta; vegetación, mobiliario, pintura y relieve desactivables.

WASD desplaza; arrastrar con botón derecho orienta; Q/E baja/sube; Shift acelera;
Esc libera el mouse. Vista aérea y nivel de calle tienen puntos predefinidos.
El selector Paisaje orienta hacia el área de Silla, Sierra Madre o Loma Larga.
Es cámara libre; no incorpora personaje físico ni garantiza colisiones.

## Datos frente a interpretación

El GLB GEO-003, sus 1.136 edificios, 2.665 vías OSM, 2.673 partes y 1.077.198
triángulos son la fuente. Los 64 sectores conservan posición, índices, colores,
metadatos y trazabilidad con error float32 menor de 0,1 mm. No se simplifican
las mallas del piloto. Muchas alturas/anchuras continúan siendo estimadas.

Las fachadas **no son la apariencia medida de cada inmueble**. No se inventan
nombres comerciales, monumentos o categorías GIS. 807 edificios conservan estilo
`unknown`; reciben un acabado genérico sin cambiar su clasificación fuente.
Los cristales son PBR opacos, sin interiores ni reflejos fotográficos.

El complemento gratuito OSM contiene 200 nodos: 43 árboles, 133 cruces, 15 controles
semafóricos y otros objetos. El generador omite objetos sin suelo exportado válido;
no convierte 610 rayas en 610 cruces. Las dimensiones, orientación y distribución
de pintura son propuestas. Las líneas requieren `lanes=1..6` y `oneway` explícito;
el separador bidireccional sólo se genera con dos carriles. No se deducen sentidos
para calles ambiguas ni se cambia el grafo vial. Las plantaciones adicionales,
bancas y luminarias se limitan a banquetas existentes y conservan `decorative=true`.
Los modelos de árbol son formas genéricas, no especies verificadas.

Las siluetas del fondo se muestrean del DEM Copernicus real (DSM ~30 m, EGM2008),
con LOD 360/180/90 m y hueco central para no tapar el piloto. Los bordes LOD
solapan bajo su contorno y el pase urbano conserva prioridad de profundidad.
Los presets de paisaje cargan los 64 sectores para evitar huecos de primer plano;
la resolución y los LOD siguen el perfil elegido. No hay montañas dibujadas
por intuición. Los presets con nombres son direcciones aproximadas; queda pendiente
verificar anotaciones de cumbres con una fuente puntual accesible y referencias
fotográficas legales. No se presenta ese fondo como un terreno transitable.

## Arquitectura reutilizable en Unreal

`tools/build_web_viewer.py --visual` añade `_MOW_STYLE` sin sustituir las posiciones,
colores ni identificadores. `world002_visual.py` decide la receta; `catalog.json`
separa parámetros de los datos originales. `world002_decor.py` genera un sidecar
con posiciones en metros X este/Y arriba/Z sur, ID fuente y banderas de inferencia.
`build_world002.py` añade el DEM regional derivado y sus hashes.

En runtime `materials.js` mantiene materiales MeshStandard PBR compartidos y shaders
procedurales; `decorations.js` agrupa originales low-poly en InstancedMesh por sector
con LOD de copas; `background.js` dibuja el DEM en un pase de profundidad independiente.
`visual.js` aplica iluminación, opciones y comparación; el planificador de FREE-001
conserva carga concurrente/abort/evicción. Los buffers propios de las instancias se
liberan al descargar y las geometrías compartidas sobreviven para reutilizarse.

Unreal podrá consumir catálogo/sidecar con conversión X=east, Y=south, Z=up,
metros ×100, pivotes por celda y EGM2008. Los shaders GLSL no son materiales Unreal;
requieren implementación equivalente y validación real en UE. Ningún asset nativo
UE se reescribe aquí; la preparación C++ de PR #2 continúa pendiente de motor.

## Automatización y validación

El workflow `world002-web.yml` obtiene la Release GEO-003 fijada y comprueba hashes,
usa el TIFF Copernicus fijado, construye en una carpeta nueva, valida toda geometría,
atributos, nodos OSM y todas las alturas LOD, ejecuta Python/Node y Chromium real.
El navegador verifica comparación, tres iluminaciones, sombras, opciones, tres
calidades, 64 sectores y ciclos de descarga. Incluye teclado/mouse y controles móviles.
No se usan cachés ni almacenamiento de Actions Artifacts; los runners son estándar
públicos gratuitos. No se contratan servicios ni se activa LFS.

`gh-pages` contiene sólo el sitio generado, bajo un tope de 50 MiB y commits sin
force-push. Los modelos/capturas no entran en la rama fuente. La URL de comparación
FREE-001 queda fijada al commit antiguo para preservarla. Pages requiere permisos
administrativos no disponibles; se mantiene la alternativa de vista previa gratuita
raw.githack, sin cuenta/tarjeta. Ese servicio externo puede mostrar un aviso con
publicidad, no tiene SLA ni garantía de cuotas. La aplicación sólo descarga recursos
estáticos del proyecto; los `.gz` pueden redirigir al mismo commit en GitHub.

Para agentes, no requiere pasos del usuario:

```bash
python tools/prepare_web_source.py --archive artifacts/input/MonterreyOpenWorld_GEO003_WORLD001.zip --output artifacts/source-city --visual
python tools/build_world002.py --city artifacts/source-city --output artifacts/world002-site
python tools/validate_web_viewer.py --city artifacts/source-city --site artifacts/world002-site
python tools/validate_world002.py --city artifacts/source-city --site artifacts/world002-site --dem artifacts/world002-inputs/regional-dem.tif --receipt artifacts/visual.json
MOW_SITE=artifacts/world002-site MOW_EVIDENCE=artifacts/evidence MOW_WORLD002=1 node WebViewer/tests/browser.mjs
```

## Límites pendientes

Continúan los 97 tramos motorizados excluidos y los cruces con problemas GEO-003.
No hay tráfico nuevo, NPCs, físicas de peatón, interiores o ciudad visualmente final.
No hay ejecución/compilación/cooking en UE. La prueba gráfica disponible usa
SwiftShader por software: sus FPS no caracterizan una GPU doméstica. Se necesita
validación posterior en GPUs reales de gama baja/media/alta; no se certifica Firefox,
Safari ni todos los móviles sólo por Chromium responsive.

Ver [licencias visuales y fuentes](../../WebViewer/visual/LICENSE.md),
[resultados verificables](RESULTADOS.md) y [compatibilidad FREE-001](../free001/ARQUITECTURA.md).
