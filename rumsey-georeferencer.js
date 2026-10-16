// Official David Rumsey Georeferencer tile exports belong here.
//
// The current Georeferencer requires a signed-in user to generate the WMTS,
// TileJSON, or XYZ URL for each processed map. Keep the complete URL, including
// its key and timestamp, private if the account/export terms require that.
// When an exported XYZ URL is added below, index.html automatically prefers it
// over the older locally cached Google Earth/KML fallback.
//
// Example shape (replace with a real export from "Use in GIS apps"):
// window.RUMSEY_GEOREFERENCER_SOURCES = {
//   "rumsey-1": {
//     georeferencerTiles:
//       "https://maps.georeferencer.com/georeferences/ID/TIMESTAMP/map/{z}/{x}/{y}.png?key=KEY",
//     georeferencerUrl:
//       "https://davidrumsey.oldmapsonline.org/maps/MAP_ID/view",
//   },
// };

window.RUMSEY_GEOREFERENCER_SOURCES = {};
