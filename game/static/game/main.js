const popColors = d3.scaleOrdinal()
  .domain(colorSchemesData.population_density.domain)
  .range(colorSchemesData.population_density.range);

const terrainColors = d3.scaleOrdinal()
  .domain(colorSchemesData.terrain.domain)
  .range(colorSchemesData.terrain.range);

const koeppenColors = d3.scaleOrdinal()
  .domain(colorSchemesData.koeppen.domain)
  .range(colorSchemesData.koeppen.range);

const colorSchemes = {
  "koeppen": koeppenColors,
  "terrain": terrainColors,
  "population_density": popColors,
};

document.addEventListener('DOMContentLoaded', () => {
  let settlements = []

  let hexLayer; // GeoJSON data for rendering
  let hexIdMap = {};

  let adjacencyMap = null;

  let settlementUpdates = {};

  let selectedHexData;
  let mapModeSelector;

  let currentYear = -8000;
  let startYear;
  let intervalID;
  let editingMode = "select";
  let selectedProperty = null;

  const map = L.map('map').setView([39.0742, 21.8243], 4); // Set the center and zoom level

  const hexDataURI = '/static/game/assets/combined_map.geojson'

  const speedSlider = document.getElementById("speed-slider");
  const yearsPerSecondDisplay = document.getElementById("years-per-second");
  const startScreen = document.getElementById('start-screen');
  const gameScreen = document.getElementById('game-screen');
  const startYearInput = document.getElementById('start-year');
  const startGameButton = document.getElementById('start-game');
  const pausePlayButton = document.getElementById('pause-play');
  const mapContainer = document.getElementById('map-container');
  const currentYearDisplay = document.getElementById('current-year');
  const entityInfo = document.getElementById('entity-info');
  const settlementInfo = document.querySelector('.settlement-info');
  const dnaInfo = document.querySelector('.dna-info');
  const settlementName = document.getElementById('settlement-name');
  const settlementPopulation = document.getElementById('settlement-population');

  const colorPalette = document.getElementById('color-palette');
  
  colorPalette.addEventListener('click', (event) => {
    const clickedElement = event.target;
    if (clickedElement.classList.contains('color-box')) {
      const prevSelectedElement = colorPalette.querySelector('.selected');
      if (prevSelectedElement) {
        prevSelectedElement.classList.remove('selected');
      }
  
      clickedElement.classList.add('selected');
      selectedColor = clickedElement.style.backgroundColor;
      selectedProperty = clickedElement.getAttribute('data-property-value');
    }
  });

  document.getElementById('pencil-tool').addEventListener('click', function() {
    editingMode = "pencil";
    this.style.color = editingMode == "pencil" ? 'red' : 'black'; // Change color to indicate active state
  });
  document.getElementById('paintbucket-tool').addEventListener('click', function() {
    editingMode = "paintbucket";
    this.style.color = editingMode == "paintbucket" ? 'red' : 'black'; // Change color to indicate active state
  });
  
  let updatesCache = {};
  const batchSize = 10000; // Adjust this based on your needs
  
  const editor = ace.edit("json-editor");
  editor.setTheme("ace/theme/chrome");
  editor.session.setMode("ace/mode/json");
  editor.session.setTabSize(2);

  const svgLayer = L.svg();
  svgLayer.addTo(map);

  const settlementLayer = L.layerGroup();
  settlementLayer.addTo(map);

  speedSlider.addEventListener("input", () => {
    adjustGameSpeed();
  });

  const downloadBtn = document.getElementById("download-json");
  downloadBtn.addEventListener("click", downloadCacheAsJSON);

  let selectedHexLayer = L.geoJSON(null, {
    style: {
      color: '#ff0000', // Set the border color of the selected hex
      weight: 3, // Set the border width of the selected hex
      fillColor: '#ff0000', // Set the fill color of the selected hex
      fillOpacity: 0.3, // Set the fill opacity of the selected hex
    },
  }).addTo(map);

  startGameButton.addEventListener('click', startGame);
  pausePlayButton.addEventListener('click', toggleGamePause);
  document.getElementById('edit-hex-json').addEventListener('click', openJSONEditor);
  document.getElementById('save-json').addEventListener('click', saveJSON);
  //document.getElementById('cancel-json').addEventListener('click', cancelJSON);

  async function loadData() {
    try {
      try {
        const response = await fetch('/game/cache_hexagon_data/');
        const data = await response.json();
        console.log("Cached hexagon data.");
      } catch (error) {
        console.error('Error caching hexagon data:', error);
      }

      try {
        const response = await fetch('/game/prepare_hex_updates/');
        const data = await response.json();
        console.log("Created hex updates on backend.");
      } catch (error) {
        console.error('Error retrieving hex updates:', error);
      }

      try {
        const response = await fetch('generate_adjacency_map/');
        const data = await response.json();
        adjacencyMap = data;
        console.log("Created and set adjacency data.");
      } catch (error) {
        console.error('Error retrieving adjacency map:', error);
      }

      await populateMapModeSelector();
      await updateMapMode();
      await updateColorPalette();
      await loadSettlements();

      console.log("Data loaded.");
    } catch (error) {
      console.error('Error processing data:', error);
    }
  }

  function startGame() {
    startScreen.style.display = 'none';
    gameScreen.style.display = 'block';
    
    startYear = parseInt(startYearInput.value, 10)
    currentYear = startYear;
    currentYearDisplay.innerText = currentYear;
    document.getElementById("hexInfo").style.display = "block";

    try {
      loadData();
    } catch {
      console("Didn't load data");
    }
    
  }

  function adjustGameSpeed() {
    clearInterval(intervalID);
    
    const yearsPerSecond = parseFloat(speedSlider.value);

    const intervalDuration = 1 / yearsPerSecond; // Seconds per year
    
    yearsPerSecondDisplay.innerText = yearsPerSecond;

    intervalID = setInterval(() => {
      currentYear++;
      currentYearDisplay.innerText = currentYear;
      updateVisibleSettlements();
      updateVisibleHexes();
    }, intervalDuration * 1000); // Convert seconds to milliseconds

    console.log("Game speed adjusted");
  }

  async function loadSettlements() {
    fetch('/static/game/assets/settlements.geojson')
      .then(response => response.json())
      .then(data => {
        // Call the drawHexagons function with the fetched GeoJSON data
        settlements = data;

        settlements.forEach((settlement) => {
          const foundingYear = settlement.properties.founding;
      
          if (foundingYear <= currentYear) {
            createSettlement(settlement);
          }

          if (!settlementUpdates[foundingYear]) {
            settlementUpdates[foundingYear] = {
              settlements: [],
              populationUpdates: {},
            };
          }
      
          settlementUpdates[foundingYear].settlements.push(settlement);
      
          const populationYears = Object.keys(settlement.properties.population).map(Number);
          populationYears.forEach((year) => {
            if (!settlementUpdates[year]) {
              settlementUpdates[year] = {
                settlements: [],
                populationUpdates: {},
              };
            }
            settlementUpdates[year].populationUpdates[settlement.id] = settlement.properties.population[year];
          });
        });
        console.log("Settlements created.");
      });
  }

  function populateMapModeSelector() {
    const MapModeSelectorControl = L.Control.extend({
      options: {
        position: 'topleft'
      },
      onAdd: function (map) {
        const container = L.DomUtil.create('div', 'map-mode-selector-container leaflet-bar');
        mapModeSelector = L.DomUtil.create('select', 'map-mode-selector', container);
  
        for (const mode in colorSchemes) {
          const option = document.createElement('option');
          option.value = mode;
          option.innerText = mode.charAt(0).toUpperCase() + mode.slice(1);
          mapModeSelector.appendChild(option);
        }
  
        mapModeSelector.addEventListener('change', (event) => {
          updateMapMode();
          updateColorPalette();
        });
  
        return container;
      }
    });
  
    const mapModeSelectorControl = new MapModeSelectorControl();
    map.addControl(mapModeSelectorControl);
  }

  // Update a single hex
  function updateSingleHex(hex) {
    const updatedHex = getStylizedHex(hex);
  
    hexLayer.removeLayer(hex);
    hexLayer.addLayer(updatedHex);
  }

  function getStylizedHex(hex) {
    const selectedMode = mapModeSelector.value;
    const selectedColorScheme = colorSchemes[selectedMode];

    return L.geoJSON(hex, {
      style: function (feature) {
        return {
          fillColor: selectedColorScheme(feature.properties[selectedMode]),
          weight: 0.3,
          opacity: 1,
          color: 'grey',
          fillOpacity: 1.0
        };
      },
      onEachFeature: function (feature, layer) { onHexClick(feature, layer) }
    });
  }

  function onHexClick(feature, layer) {
    layer.on({
      click: function(e) {
        switch (editingMode) {
          case 'pencil':
            feature.properties[mapModeSelector.value] = selectedProperty;
            updateSingleHex(feature);
            break;
          case 'paintbucket':
            floodFill(feature, selectedProperty);
            break;
          default:
            // Original click handling code
            showHexInfo(feature);
            selectedHexData = feature;
            selectedHexLayer.clearLayers();
            selectedHexLayer.addData(feature.geometry);
        }
      }
    });
  }
  

  async function fetchHexUpdatesInBatch(currentYear) {
    const fetchStartYear = -1 * (Math.floor(currentYear / batchSize) * batchSize);
    const fetchEndYear = (fetchStartYear - batchSize + 1);
    
    const response = await fetch(`get_hex_updates_range/${fetchStartYear}/${fetchEndYear}/`);
    const updates = await response.json();
    
    for (const year in updates) {
      updatesCache[year] = updates[year];
    }
  }

  function updateVisibleHexes() {
    console.log("Updating hexes for currentYear " + currentYear);
    if (!updatesCache[currentYear]) {
      fetchHexUpdatesInBatch(currentYear).then(() => {
        applyUpdates(currentYear);
      });
    } else {
      applyUpdates(currentYear);
    }
  }
  
  function applyUpdates(year) {
    const updates = updatesCache[year];
    if (updates && Object.keys(updates).length > 0) {
      hexLayer.toGeoJSON().features.forEach((hex) => {
        const update = updates[hex.properties.id];
        if (update) {
          hexProperties.forEach((hexProperty) => {
            if (update[hexProperty]) {
              hex.properties[hexProperty] = update[hexProperty];
              updateSingleHex(hex);
            }
          });
        }
      });
    }
  }

  // Display information about the clicked hex
  function showHexInfo(feature) {
    const properties = feature.properties;
  
    document.getElementById("hex-terrain").textContent = properties.terrain;
    document.getElementById("hex-climate").textContent = properties.climate;
    document.getElementById("hex-koeppen").textContent = properties.koeppen;
    document.getElementById("hex-resources").textContent = properties.resources;
    document.getElementById("hex-agriculture-adoption").textContent = properties.agriculture_adoption;
    document.getElementById("hex-trade-route-quality").textContent = properties.trade_route_quality;
    document.getElementById("hex-caloric-surplus").textContent = properties.caloric_surplus;
    document.getElementById("hex-population-density").textContent = properties.population_density;
  
    document.getElementById("hexInfo").style.display = "block";
  }
  

  async function updateMapMode() {
    // If hexLayer exists, loop through its layers and update the style based on the new map mode
    if (hexLayer) {
      hexLayer.eachLayer((layer) => {
        const selectedMode = mapModeSelector.value;
        const selectedColorScheme = colorSchemes[selectedMode];
  
        layer.setStyle((feature) => {
          return {
            fillColor: selectedColorScheme(feature.properties[selectedMode]),
            weight: 0.3,
            opacity: 1,
            color: "grey",
            fillOpacity: 1.0,
          };
        });
      });
    } else {
      const response = await fetch(`get_current_hexes/${-1 * startYear}/`);
      const currentHexes = await response.json();
      
      hexLayer = L.layerGroup();
  
      // Loop over the hexagons and add them to the layer group
      currentHexes.forEach((hex) => {
        hexIdMap[hex.properties.id] = hex;
        hexLayer.addLayer(getStylizedHex(hex));
      });
  
      hexLayer.addTo(map);
      console.log("Added hex layer to map");
    }
  }
  

  function createSettlement(settlement) {
    if (settlement.properties.founding <= currentYear) {
      // Create an icon for the settlement
      const settlementIcon = L.icon({
        iconUrl: '/static/game/assets/settlement-icon.png',
        iconSize: [32, 32], // Set the size of the icon
      });
    
      // Create a Leaflet marker
      const marker = L.marker([settlement.geometry.coordinates[1], settlement.geometry.coordinates[0]], {
        icon: settlementIcon,
        zIndexOffset: 1000, // Set a high zIndex to ensure the icons are rendered above the map
      });
    
      // Add the marker to the settlementLayer
      settlementLayer.addLayer(marker);
    
      // Attach a click event to the marker
      marker.on("click", () => {
        settlementName.textContent = settlement.properties.name;
        const populationYears = Object.keys(settlement.properties.population).map(Number);
        const validYears = populationYears.filter((year) => year <= currentYear);
        
        if (validYears.length > 0) {
          const latestYear = Math.max(...validYears);
          const currentPopulation = settlement.properties.population[latestYear];
          settlementPopulation.innerText = `Population: ${currentPopulation}`;
        } else {
          settlementPopulation.innerText = `Population: N/A`;
        }

        settlementInfo.style.display = 'block';
        dnaInfo.style.display = 'none';
      });
    }
  }

  function updateVisibleSettlements() {
    if (settlementUpdates[currentYear]) {
      settlementUpdates[currentYear].settlements.forEach(settlement => {
          createSettlement(settlement)
      });
    }
  }

  function toggleGamePause() {
    if (intervalID) {
        clearInterval(intervalID);
        intervalID = null;
        pausePlayButton.innerText = 'Play';
    } else {
        intervalID = setInterval(() => {
        currentYear++;
        currentYearDisplay.innerText = currentYear;
        }, 1000);
        pausePlayButton.innerText = 'Pause';
    }
  }

  async function openJSONEditor() {
    if (selectedHexData) {
      if (!(intervalID)) {
        toggleGamePause(); // Pause while we edit
      }

      // TODO don't let us click on another tile
  
      // Get the tile value with all historical properties
      const response = await fetch(`get_hex_by_id/${selectedHexData.properties.id}/`);
      const ogHexWithID = await response.json();

      editor.setValue(JSON.stringify(ogHexWithID, null, 2), -1);

      document.getElementById("hexInfo").style.display = "none";
      document.getElementById("json-editor-container").style.display = "block";
    }
  }

  async function saveJSON() {
    try {
      const newHexData = JSON.parse(editor.getValue());
      const hexId = selectedHexData.properties.id;

      if (newHexData.properties.id !== hexId) {
        alert("Invalid JSON. ID must be " + hexId);
      }
  
      const response = await fetch(`/game/update_hex_by_id/${hexId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newHexData)
      });
  
      if (response.ok) {
        document.getElementById("json-editor-container").style.display = "none";
        document.getElementById("hexInfo").style.display = "block";
  
        alert("Hex saved successfully to cache");
      } else {
        throw new Error("Failed to update hex data");
      }
    } catch (error) {
      alert("Invalid JSON. Please check your input and try again.");
    }
  }

  function downloadCacheAsJSON() {
    let hexagonData;
  
    fetch('get_hexagon_data/')
      .then(response => response.json())
      .then(data => {
        hexagonData = data;
        console.log('hexagonData:', hexagonData);
        const encodedData = encodeURIComponent(JSON.stringify(hexagonData));
        const dataUrl = "data:text/json;charset=utf-8," + encodedData;
        console.log('dataUrl:', dataUrl);
        downloadBtn.setAttribute("href", dataUrl);
        downloadBtn.setAttribute("download", "hexagon_data.json");
        downloadBtn.click();
      });
  }

  function updateColorPalette() {
    const selectedMode = mapModeSelector.value;
  
    // Clear the existing color palette
    while (colorPalette.firstChild) {
      colorPalette.removeChild(colorPalette.firstChild);
    }
  
    // Populate the color palette with the unique colors
    for (let propertyValue in colorSchemesData[selectedMode].domain) {
      let color = colorSchemes[selectedMode](colorSchemesData[selectedMode].domain[propertyValue]);
      let colorDiv = document.createElement('div');
      colorDiv.style.backgroundColor = color;
      colorDiv.className = 'color-box';  // Assign class
      colorDiv.title = `Color: ${color}\nProperty value: ${colorSchemesData[selectedMode].domain[propertyValue]}`;  // Add title attribute
      colorDiv.dataset.color = color; // Store the color in a data attribute for retrieval on click
      colorDiv.dataset.propertyValue = colorSchemesData[selectedMode].domain[propertyValue];
      colorPalette.appendChild(colorDiv);
    }
  }
  
  function floodFill(hex) {
    if (adjacencyMap === null) {
      console.error("Adjacency map is not loaded.");
      return;
    }
    if (selectedProperty === null) {
      console.error("No selected property");
      return;
    }

    if (hex.properties[mapModeSelector.value] == selectedProperty) {
      console.log("No need to fill this hex");
    }

    const queue = [hex];
    const targetValue = hex.properties[mapModeSelector.value];
  
    while (queue.length > 0) {
      const currentHex = queue.pop();
      if (currentHex.properties[mapModeSelector.value] !== targetValue) {
        continue;
      }
  
      currentHex.properties[mapModeSelector.value] = selectedProperty;
      updateSingleHex(currentHex);
  
      const adjacentHexes = adjacencyMap[currentHex.properties.id].map(id => hexIdMap[id]);

      console.log("adjacent hexes to hex " + currentHex.properties.id + ": " + adjacentHexes.length);

      for (const adjacentHex of adjacentHexes) {
        if (adjacentHex.properties[mapModeSelector.value] === targetValue) {
          queue.push(adjacentHex);
        }
      }
    }
  }
  
});



