# Resultados GEO-004

Validación numérica completada, separada de exactitud topográfica y de pruebas
Unreal. La comprobación del navegador y publicación se registra al terminar sus
recibos; no se declara éxito por anticipado.

El baseline conserva su GLB SHA256
`c07d1a91e37bea063c638cb51275a770ed0ab222c7a2b6c49f6a7dc30436bcfc`.
Los inputs GIS originales y el proyecto UE5.6.1 se verifican sin modificaciones.
La nueva fuente es INEGI G14C26A3, datos 2007, producto 5 m, EPV desconocida.

## Qué se compara

| Medición geométrica | GEO-003 observado | GEO-004 medido |
| --- | ---: | --- |
| Triángulos de tapa vial a nivel separados >25 cm de su propio soporte | 10.569 | 0 |
| Piezas a nivel con faldón vertical >1 m | 195 | 0 |
| Máximo faldón a nivel | 7,645 m | 0,25 m; base delgada sobre el mismo MDT |
| Pendiente máxima del raster de soporte | 133,37 % | 59,24 %; pendiente nativa, sin aplanado |
| Modificaciones inducidas del terreno natural | Delta −6,689 a +5,599 m | Ninguna deformación para acomodar perfiles viales |
| Huellas y alturas relativas de edificios | 1.136 | 1.136 conservados; delta XY 0; altura relativa sin cambios |
| Tramos / aristas dirigidas | 2.665 / 4.194 | 2.665 / 4.194 conservados; delta XY 0 |

Los 25 cm son un umbral de discrepancia **entre superficies generadas**, no la
precisión de INEGI. Los 1 mm de costura son tolerancia de intercambio numérico,
no exactitud del levantamiento. Un gradiente natural alto se revisa, no se elimina
por superar un límite de conducción arbitrario.

## Comprobaciones completas

- 201 cruces entre niveles comprobados: 0 interferencias potenciales de pisos/techos/tableros en las superficies presentes; 15 cruces con superficie ausente permanecen pendientes.
- 81 apoyos estimados contrastados con el tablero exportado: 0 huecos >25 cm. No demuestra diseño estructural real.
- 0 piezas de puente con terreno >25 cm por encima de su tablero en los triángulos comprobados.
- 0 edificios a nivel con base flotante >50 cm en el perímetro muestreado; 0 techos atravesados por los puntos del terreno comprobados (perímetro e interior de retícula nativa). **98 cimentaciones requieren revisión** por variación topográfica, sin aplanar el terreno.
- 336 ejes tienen muestras sin su superficie correspondiente, antes y después; no se ocultan sus recortes/roles superpuestos.
- Costura respecto al mismo MDT canónico: máximo 9,40e−8 m; 12 muestras caen en huecos explícitos de portales. Son tolerancias numéricas, no precisión del origen.
- 0 triángulos degenerados tras intercambio float32. Modelo nuevo: 2.757 piezas / 1.386.231 triángulos; la mayor densidad conserva los cambios de plano nativos.
- 0 deformaciones del raster para adaptar carreteras. Aberturas locales de portales: 6.598,35 m² frente a 17.101,6 m² de excavación de corredor previo.
- 622 puntos adicionales de revisión (pendiente longitudinal, superficie faltante, cruce o cimentación) además de la auditoría de tapas; todos alimentan el mapa del visor.
- 97 pruebas Python y 8 Node aprobadas localmente. Las pruebas de CI identifican su commit exacto.

Nuevo GLB SHA256: `102833aa723739bf9021a1493412ed38a316011153d951724092226f4c5638cf`.
[QA numérico local](local-validation.json) · [Auditoría resumida](local-audit-summary.json).

## Pendientes que no se ocultan

- No hay puntos de control oficiales independientes del piloto adquiridos con los que certificar exactitud absoluta. La antigüedad 2007 y la realización GGM05/GGM10 permanecen como incertidumbres.
- Hay superficies de ejes ausentes ya en GEO-003 por recorte contra edificios o solape de roles. No se sustituyen por otro nivel para simular un éxito.
- Los cruces entre niveles con superficie ausente, las cimentaciones con relieve >2 m y las estructuras sin cotas levantadas quedan en GeoJSON, CSV y mapa de calor.
- Puentes, túneles, apoyos y portales siguen siendo estimaciones geométricas, no ingeniería civil validada. No se certifican gálibos, seguridad ni mundo completamente conducible.
- La comparación de raster Copernicus / INEGI combina tipo de modelo y épocas distintas; no permite atribuir cada diferencia a un error de medición.
- Las pruebas Chromium usan SwiftShader por software. No se extrapolan FPS a GPU comerciales ni a otros navegadores no ejecutados.
- Unreal no está disponible: no se ejecutaron importación, compilación, colisiones ni gameplay. Se conservan los exports estáticos y coordenadas para integración posterior.

Siguiente paso técnico: resolver primero las zonas señaladas con controles
independientes, trazado de superficies faltantes y cotas estructurales legales;
no continuar añadiendo personajes o tráfico sobre incidencias sin resolver.
