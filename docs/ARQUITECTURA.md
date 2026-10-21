# Dirección técnica inicial

Objetivo confirmado: UE5, Windows PC, mundo abierto metropolitano, escala métrica
1:1, conducción realista equilibrada y máxima prioridad a fidelidad geográfica y
visual. Esta entrega prepara las herramientas geoespaciales; no es una ciudad
jugable ni un proyecto AAA completo.

## Contrato de coordenadas GEO-001.1

- Horizontal: EPSG:32614, WGS84 / UTM 14N, coordenadas de doble precisión.
- Centro provisional heredado: latitud 25.667, longitud −100.310. No se interpreta como límite
  oficial de toda la Zona Metropolitana de Monterrey.
- Mundo UE: X este de cuadrícula, Y sur de cuadrícula, Z arriba, centímetros.
  Origen horizontal en el centro; alturas relativas al cero del datum de origen.
- Las filas del raster van de norte a sur. La convención propuesta usa Y positivo
  hacia el sur y no invierte filas. Su aplicación real debe verificarse en UE.
- El actor Landscape comienza en la esquina noroeste de cada tesela. Su X/Y,
  desplazamiento Z y cuatro puntos de control están en `manifest.json`.
- Elevación: `Z_cm = actor_Z_cm + (valor_uint16 - 32768) * escala_Z / 128`.
- 505 vértices por eje: 4 componentes × 2 secciones × 63 quads + 1.
  No son 505 metros: manda `sample_spacing_m`.

UTM tiene distorsión. En el centro, el factor es aproximadamente
0.9998134481 y la convergencia −0.567495 grados. Son metros de cuadrícula;
una longitud de cuadrícula de 2 km corresponde aproximadamente a 2000.373 m
sobre el terreno al usar el factor central. No se promete equivalencia geodésica
exacta 1:1. Antes de fijar toda la metrópoli se evaluará una proyección local y
su presupuesto de error; no se cambia silenciosamente el CRS heredado.

## Organización

`GeoPipeline/` contiene exportación, adquisición, validación y capa urbana.
`tests/` usa datos analíticos y OSM ficticio, sin depender de Internet.
`Data/raw/`, `Data/unreal/` y `Data/urban/` son datos locales ignorados por Git.
`Unreal/MonterreyOpenWorld/` contiene un descriptor y configuración inicial;
no incluye mapas `.umap`, assets `.uasset`, código de gameplay ni compilación.
`docs/` conserva diagnóstico, procedencia y fuentes. `artifacts/` guarda resultados
y paquetes de revisión, sin incorporar binarios grandes al control de versiones.

Las salidas no se sobreescriben. Para repetir una exportación se usa un directorio
nuevo; la validación y las pruebas sí pueden repetirse sin modificar datos fuente.
Dependencias fijadas en `requirements.lock.txt`; `requirements.txt` declara rangos.
No se crean worktrees: cada tarea cloud ya está aislada.

## Alcance urbano implementado

Entrada: JSON Overpass con nodos completos y vías. Salida: grafo dirigido,
polilíneas recortadas en centímetros locales y huellas GeoJSON WGS84 con tags.
Se dividen vías en nodos compartidos y se conservan sentido, `bridge`, `tunnel`,
`layer`, anchura y carriles originales. No se crean conexiones por intersección
geométrica; los nodos OSM determinan la conectividad. No es todavía un grafo de
carriles ni un navegador: faltan restricciones de giro, accesos e inferencias viales.

Los edificios simples y relaciones multipolígono válidas se recortan. Se unen
cadenas de contorno completas, se preservan patios interiores y se evitan
miembros duplicados. Anillos incompletos o inválidos se contabilizan, sin reparación
silenciosa. Z de calles y bases de edificios permanece `null`. No se aplana un
puente sobre el DSM. No se fabrican alturas donde no exista una etiqueta métrica.

## Próximos hitos y dependencias

1. **GEO-002**: ampliar el piloto real ya descargado; comparar Copernicus con
   CEM/DTM/LiDAR disponible y validar elevaciones con controles independientes.
   Ejecutar las herramientas preparadas; no pedir al usuario que programe.
2. Importador UE automatizado en un runner con editor licenciado. Verificar
   Landscape, orientación, materiales y distancias mediante puntos de control;
   guardar un mapa real y pruebas de editor. El descriptor por sí solo no lo hace.
3. Extender relaciones complejas y extracción regional PBF, alturas del terreno,
   calzadas, puentes y mallas de edificios con procedencia de cada dato.
4. World Partition, streaming, HLOD, presupuestos de rendimiento y un bloque
   urbano fiel antes de extender toda la metrópoli.
5. Prototipo de vehículo y conducción, con superficies, colisiones y pruebas en
   Windows. No seleccionar parámetros físicos sin validar el espacio geográfico.

Decisiones de alcance, presupuesto, adquisición comercial de datos o cambio de
motor requieren supervisión; correcciones y automatización rutinarias continúan
de forma autónoma. No se compran recursos, publica el repositorio ni acepta una
licencia privada en nombre del usuario como parte de esta entrega.
