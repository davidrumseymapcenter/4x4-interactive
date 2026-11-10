// Official David Rumsey Georeferencer tile exports belong here.
//
// Prefer a public Allmaps annotation backed by the map's official Rumsey IIIF
// scan. If only a signed Georeferencer export exists, keep its key private when
// the account/export terms require that. index.html prefers every verified XYZ
// source here over the older locally cached Google Earth/KML fallback.
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

window.RUMSEY_GEOREFERENCER_SOURCES = {
  "rumsey-10": {
    georeferencerTiles:
      "https://allmaps.xyz/manifests/c047e9dd35f2d377/{z}/{x}/{y}@2x.png",
    georeferencerUrl:
      "https://viewer.allmaps.org/?url=https://www.davidrumsey.com/luna/servlet/iiif/m/RUMSEY~8~1~308707~90078572/manifest",
    georeferencerMinZoom: 0,
    georeferencerMaxZoom: 22,
  },
};
