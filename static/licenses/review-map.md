# Mappa di revisione dei luoghi

La mappa interattiva dell'editor usa risorse incluse nell'app e funziona senza
connessione. È una base geografica moderna di orientamento: non rappresenta
confini, coste ricostruite o sovranità dell'epoca del documentario. Non viene usata
come sostituzione automatica delle mappe del film.

## Leaflet 1.9.4

- Autori: Volodymyr Agafonkin, CloudMade e contributori Leaflet.
- Licenza: BSD 2-Clause; testo completo incluso in
  [`../vendor/leaflet/LICENSE`](../vendor/leaflet/LICENSE).
- [Download ufficiale e versione stabile](https://leafletjs.com/download.html).
- [Codice sorgente della versione 1.9.4](https://github.com/Leaflet/Leaflet/tree/v1.9.4).
- I file di distribuzione sono stati scaricati da
  `https://unpkg.com/leaflet@1.9.4/dist/`, collegamento indicato dal sito Leaflet,
  e sono serviti localmente. Nessun CDN viene richiesto dal browser a runtime.
- SHA-256 `leaflet.js`:
  `db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a`.
- SHA-256 `leaflet.css`:
  `a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6`.

## Natural Earth: coste e terre emerse

- Dati: Natural Earth, Tom Patterson, Nathaniel Vaughn Kelso e contributori.
- Licenza: pubblico dominio. [Condizioni ufficiali](https://www.naturalearthdata.com/about/terms-of-use/).
- Origine: `ne_10m_land.geojson`, [repository Natural Earth Vector](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_land.geojson),
  già acquisito dalla pipeline come `assets/geography/land.geojson`.
- Elaborazione: semplificazione Douglas–Peucker a 0,1 gradi; coordinate WGS84
  arrotondate a quattro decimali. Si conservano vertici originali per le isole
  sotto la tolleranza e per quelle troppo piccole per l'arrotondamento. Nessun
  attributo del file originale o dato di un progetto è presente nell'output.
- Rigenerazione dal file locale immutato:
  `python scripts/build_review_map.py --source pipeline/assets/geography/land.geojson`.
  Usa solo la libreria standard di Python e non richiede download.
- SHA-256 del file sorgente usato:
  `1ac90796408bc6ad6911d69448485d3c4dbf2190370080368a09976e1c9f7416`.
- SHA-256 di `static/maps/world-land.geojson`:
  `d21d1ec11397416e925701887906c871d158e6af67d110c88a396fbbc0ada4f3`.
- Dimensione: 833.872 byte. Il file è già incluso nello ZIP e nel repository.

## Dettaglio OpenStreetMap facoltativo

L'utente può attivare il dettaglio online per orientarsi a scala locale. Le
tessere restano un servizio esterno e non fanno parte della distribuzione.

- Dati: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
- [Politica d'uso delle tessere raster](https://operations.osmfoundation.org/policies/tiles/).
- URL: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
- Solo visualizzazione interattiva corrente, cache HTTP normale del browser;
  nessun download massivo, prefetch o archivio offline di tessere.
- L'attribuzione resta visibile sulla mappa. La richiesta delle tessere conserva
  il Referer del browser tramite la policy del singolo elemento immagine.
- I dati e i nomi sono moderni, non una fonte indipendente di localizzazioni o
  confini storici. Le coordinate spostate dall'utente sono correzioni manuali.

Fonti e versione consultate il 5 settembre 2026.
