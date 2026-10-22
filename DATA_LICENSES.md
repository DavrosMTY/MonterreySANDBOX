# Geographic data notices

Only the small, reviewed Monterrey pilot is included in Git. No Unreal Engine
binary/source distribution, paid map data, third-party commercial assets, caches
or unreviewed downloads are included. Project source publication does not grant a
new general redistribution license for the game code; that license remains for
the owner to choose. The following separate terms apply to geographic data.

## Copernicus GLO-30 pilot and derivatives

produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and
Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
all rights reserved.

The organisations in charge of the Copernicus programme by law or by delegation
do not incur any liability for any use of the Copernicus WorldDEM-30.

No endorsement by the provider, licensor, ESA, the European Union or any entity
responsible for Copernicus is implied. Subsequent users distributing this data or
its derivatives must retain the attribution, modified-data notice, liability
notice and all obligations in Article 6 of the accompanying license.

Full terms: [Copernicus GLO-30-F license](docs/sources/COPERNICUS_GLO30_LICENSE.txt).
The license grants reproduction, distribution, public communication and adaptation
in Article 4; the free-use conditions in Articles 5 and 6 remain applicable.
Review evidence: `docs/sources/legal-evidence.json` and
`Data/raw/copernicus_reviewed.source.json`. The pilot is a DSM, not bare-earth DTM.

## OpenStreetMap

© OpenStreetMap contributors. Source extract and derived geographic databases are
available under the [Open Database License 1.0](docs/sources/ODbL-1.0.txt).
See https://www.openstreetmap.org/copyright for attribution and rights.

The original pilot extract is supplied as `Data/raw/osm.json` with provenance.
Editable derived databases are supplied in `Data/urban/monterrey_centro_v3/`.
Retain attribution and the applicable ODbL obligations when sharing databases or
produced works. This notice also accompanies the downloadable Release packages.

## Complemento WORLD-002

El inventario `WebViewer/visual/osm-street-inventory.json` contiene 200 nodos OSM
(consulta y SHA256 en el archivo `.source.json` adjunto), © OpenStreetMap contributors,
ODbL 1.0. Se distribuye como fuente de la capa derivada; no modifica el piloto original.
El fondo de ±18 km deriva del mismo mosaico Copernicus revisado, conserva su aviso
y no constituye un DTM ni terreno jugable. Recetas y arte generado originales:
CC0 1.0 sólo para esos parámetros/texturas/formas, sin relicenciar el código del juego.
Ver [inventario de licencias visuales](WebViewer/visual/LICENSE.md).
