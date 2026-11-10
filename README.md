# 4x4 Interactive

This is a spinning globe display with historical-map overlays, built for the interactive 4x4 presentation screen in the Stanford David Rumsey Map Center. You can pan, zoom, and compare historical maps with modern basemaps. The historical maps come from the [David Rumsey Map Collection](https://www.davidrumsey.com).

## Project structure

- `index.html` — application interface and map behavior.
- `rumsey-maps.js` — generated catalog, coordinates, metadata, and overlay paths.
- `rumsey-previews/` — compact lossless WebP/JPEG KML fallback overlays.
- `rumsey-mosaics/` — larger lossless WebP overlay chunks for detailed maps.
- `rumsey-georeferencer.js` — verified IIIF-backed Allmaps tile overrides.
- `rumsey-georeferencer.js` — verified high-resolution georeferencer sources.
- `stairwell-maps.js` — Stairwell Map records and metadata.
- `*_rumsey_*.py` and `build_rumsey_mosaics.py` — maintenance tools; they are not loaded by the website.

Run the site from this directory with a local web server, then open `http://localhost:8000/index.html`. Do not open `index.html` directly with a `file://` URL because browser security rules can block map assets.

## Documentation

The application uses MapLibre for its globe and modern basemaps, with georeferenced historical-map overlays and custom navigation controls. See the [project documentation](DRMCwebmapDoc/MapboxInteractiveGlobeProjectDocumentation.md) for more background.

Historical overlays prefer public Allmaps XYZ tiles generated from the official
David Rumsey IIIF master scan. These load source regions at the appropriate
resolution as the viewer zooms. A local WebP georeference remains available for
catalog records that have no published Allmaps annotation; a plain IIIF image
cannot be positioned accurately without that annotation.
