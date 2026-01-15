### To view this interactive map, click on [this link](https://davidrumseymapcenter.github.io/4x4-interactive/)

>[!info] Helpful References
>- Mapbox Documentation: [Mapbox Documentation found here](https://docs.mapbox.com/mapbox-gl-js/guides/install/)
>	Helpful for building new features onto your web map
>- Stanford Webmap Workshop Documentation:[Evan's Web Map Workshop Github](https://davidrumseymapcenter.github.io/overlaying-the-past/publishing/github-account/)
>	Helpful to get started on building a web map from scratch

>[!tip] Vision for This Project
>- Spinning Globe Display on the 4x4 screen in the Map Center
>- Student Project Display: Show student's project work at the Map Center
>- Tour Display: show some historic maps, e.g. timeline of evolution of SF city 

---
## Github Work Flow for this Project Contribution
> - Clone the [Github Repository](https://github.com/davidrumseymapcenter/4x4-interactive) to your local computer
> - Create issues detailing the tasks needed to be done on the webmap
> 	- after creating the issues, claim issues you want to work on by assigning them to yourself
> - For every issue you work on, create a branch pulling from `main` branch.
> 	- Example format of the branch: `1-add-reset-button`
> - Once you are done, create a pull request to merge your branch into main, but do not do the merging itself
> 	- We will review the changes, and merge your branch with `main` once we feel ready!
> - Then resolve the issue you just finished 
> - Eventually, in order for the changes you make to go into effect on the webpage display, we need to merge the `main` branch into `publish` 
---
## Creating a spinning base globe
1.  Make sure you download the `mapbox-gl` npm package
	   Do this in your terminal: 
	   - `brew install node`
	   - `npm install mapbox-gl`
2. Create a `.html` file in your folder, and paste the code block in 
3. Replace the corresponding with our Mapbox Public Access Token
Here is a slim-down structure of the HTML script which renders the webpage:
```HTML
<html>
	<head> <!-- contains metadata and external links-->
		<style> ... </style> <!-- contains inline CSS for styling elements-->
	</head>
	<body> <!-- contains the main content of webpage-->
		<style> ... </style>
		<div id="map"></div> <!-- this is the container for content-->
		<div class="map-overlay top">
			<div class="map-overlay-inner">
				<label> ... </label> <!-- provide text for a control-->
				<input ... /> <!-- takes input for interactive form control -->
			</div>
		</div>
		<script> <!-- Javascript code -->
		...
		</script>
	</body>
</html>
```
---
## Overlay Historic map onto the globe
1. Find the map on David Rumsey Map Collection Website or Stanford's Search Work
	- Locate the IIIF Manifest of the map 
	![[Screenshot 2025-08-22 at 1.53.05 PM.png]]
	
2. Georeference this map with Allmaps with IIIF manifest 
	- Enter IIIF manifest on [Allmaps](https://editor.allmaps.org/)  to georeference the map
	![[Screenshot 2025-08-22 at 2.29.32 PM.png]]
	- Click on "Draw Mask" to draw a mask over the region where you want to crop out
	![[Screenshot 2025-08-22 at 3.27.05 PM.png]]
	- Once you are done adjusting the georeferencing, click results. Copy the URL link for the XYZ map tiles. Now this link hosts the geoferenced map tiles, which completes the georeferencing step!
	![[Screenshot 2025-08-22 at 3.29.49 PM.png]]
3. Place georeferenced map on the basemap layer by adding it into html 
```HTML 
// Add a raster source to the map.

map.on("load", () => {

// This is an event listener that waits for the map to load before adding the source and layer.

map.addSource("yourID", {

type: "raster",

tiles: [

"https://allmaps.xyz/...", // Replace with your own tile URL

],

tileSize: 256,

});

  

map.addLayer({

id: "historical-overlay",

source: "yourID",

type: "raster",

});

});
```
---

## Adding Cool Interactive Map Features
Now we have a basic spinning globe and maps that are overlaid on the spinning globe, we want to add some cool features to make the map interactive. This is where Mapbox comes in handy: it will provide tools for customizing. 
#### 1. Reset/ Spin the Globe Button
This button resets the map, and starts the spinning globe display again. 
#### 2. Project Menu 
This menu bar shows a list of all the map projects on display. 
### 3. Transparency bar to toggle 
You could change the opacity of the maps, and compare old maps with modern map
### 4. Show a Location pop up for the DRMC
Shows the location of DRMC on the spinning globe. [Example guide on mapbox here](https://docs.mapbox.com/mapbox-gl-js/example/popup/). 
### 5. Set up a Menu Button

---
