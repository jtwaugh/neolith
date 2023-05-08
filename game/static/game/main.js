const popColors = d3.scaleOrdinal()
  .domain(
    [
      0.0,
      0.1,
      0.3,
      0.5,
      0.8,
      1.5,
      1.0,
      2.0,
      5.0,
    ]
  )
  .range(
    [
      "#000000",
      "#383838",
      "#555555",
      "#717171",
      "#8D8D8D",
      "#aaaaaa",
      "#c6c6c6",
      "#e2e2e2",
      "#ffffff",
    ]
  )

const terrainColors = d3.scaleOrdinal()
  .domain(["Ice", "Water", "Plains", "Mountains"]) // Add as many terrain types as you have
  .range(["#2ca02c", "#184a85", "#ff7f0e", "#d62728"]); // Add corresponding colors for each terrain type

const koeppenColors = d3.scaleOrdinal()
  .domain([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]) // Add as many terrain types as you have
  .range(
    [
      "#184a85", 
      "#1c00ff", 
      "#3183ff", 
      "#61b2f3", 
      "#f40000", 
      "#f8a09f", 
      "#f1af00", 
      "#fce163", 
      "#feff00", 
      "#cdce00", 
      "#a0a100", 
      "#abff9b", 
      "#7bd069", 
      "#4aa12d", 
      "#d2ff44", 
      "#83ff48", 
      "#54ce00", 
      "#f500ff", 
      "#c700d2",
      "#9b37a3", 
      "#9e6fa2", 
      "#b6b8ff", 
      "#6a83e5", 
      "#585ac1", 
      "#380095", 
      "#57ffff", 
      "#5cceff", 
      "#2a8889", 
      "#164f6d", 
      "#bbbbbb", 
      "#717170"
    ]
  );

const hexProperties = ["terrain", "climate", "koeppen", "population_density"]    

const colorSchemes = {
  "koeppen": koeppenColors,
  "terrain": terrainColors,
  "population_density": popColors,
};

document.addEventListener('DOMContentLoaded', () => {
  let settlements = []

  let hexLayer; // GPT doesn't really know what this is supposed to do
  let hexagonData; // Raw data containing hex history, probably containing duplicates that aren't actually updates. TODO remove duplicate values
  let currentHexes; // Hexes starting from current year
  let hexUpdates = {}; // Diffs
  let settlementUpdates = {};

  let selectedHexData;
  let mapModeSelector;

  let currentYear = -8000;
  let intervalID;

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
  document.getElementById('cancel-json').addEventListener('click', cancelJSON);

  function startGame() {
    startScreen.style.display = 'none';
    gameScreen.style.display = 'block';
    
    currentYear = parseInt(startYearInput.value, 10);
    currentYearDisplay.innerText = currentYear;
    document.getElementById("hexInfo").style.display = "block";

    fetch(hexDataURI)
    .then(response => response.json())
    .then(data => {
      hexagonData = data;
      prepareHexUpdates(); // Turn hexes into just their updates TODO remove duplicates
      createCurrentHexes(); // Set the current values of the hexes
      populateMapModeSelector();
      updateMapMode();
    })
    .catch(error => console.error('Error fetching GeoJSON data:', error));

    
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
    });

    adjustGameSpeed();
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
        });
  
        return container;
      }
    });
  
    const mapModeSelectorControl = new MapModeSelectorControl();
    map.addControl(mapModeSelectorControl);
  }

  function createCurrentHexes() {
    if (hexagonData) {
      if (!currentHexes) {
        currentHexes = hexagonData.features.map((hex) => {
          let updatedHexProperties = {"id": hex.properties.id};
          hexProperties.forEach((property) => {
            const propertyYears = Object.keys(hex.properties[property]).map(Number);
            const validYears = propertyYears.filter((year) => year <= currentYear);
            if (validYears.length > 0) {
              const latestYear = Math.max(...validYears);
              updatedHexProperties[property] = hex.properties[property][latestYear];
            }
          });
          return Object.assign({}, hex, {
            properties: updatedHexProperties,
          });
        });
      }
    }
  }

  function renderCurrentHexes() {
    if (hexLayer) {
      // If hexLayer exists, we remove it from the map and draw a new one with the updated hexes
      map.removeLayer(hexLayer);
    }
  
    hexLayer = L.layerGroup();
  
    // Loop over the hexagons and add them to the layer group
    currentHexes.forEach((hex) => {
      hexLayer.addLayer(getStylizedHex(hex));
    });
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

  function onHexClick(hex, layer) {
    layer.on({
      click: function() {
        showHexInfo(hex);
        selectedHexData = hex;
        // Clear any existing geometry from the selectedHexLayer
        selectedHexLayer.clearLayers();
  
        // Add the clicked hex geometry to the selectedHexLayer
        selectedHexLayer.addData(hex.geometry);
      },
    });
  }
  

  // Pick out hexes that need the update and update them
  function updateVisibleHexes() {
    if (hexUpdates[currentYear]) {
      currentHexes.forEach((hex) => {
        const update = hexUpdates[currentYear][hex.properties.id];
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
  

  function updateMapMode() {
    // Remove the existing hex layer
    if (hexLayer){
      map.removeLayer(hexLayer);
    }
  
    // Redraw the hexagons with the new color scheme
    if (hexagonData){
      renderCurrentHexes(); // Render the hexgons to the hexLayer object
      hexLayer.addTo(map); // Actually add it to the map object
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

  function prepareHexUpdates() {
    const properties = ["terrain", "climate", "koeppen", "population_density"]

    const previousHexValues = {};

    if (hexagonData) {
      hexagonData.features.forEach((hex) => {
        properties.forEach((property) => {
          const propertyYears = Object.keys(hex.properties[property]).map(Number);
          propertyYears.forEach((year) => {
            const currentValue = hex.properties[property][year];
            const previousValue = previousHexValues[hex.properties.id] ? previousHexValues[hex.properties.id][property] : undefined;

            if (currentValue !== previousValue) {
              if (!hexUpdates[year]) {
                hexUpdates[year] = {};
              }
              if (!hexUpdates[year][hex.properties.id]) {
                hexUpdates[year][hex.properties.id] = {}
              }
              hexUpdates[year][hex.properties.id][property] = hex.properties[property][year]

              // Update the previous value for this property and hexagon
              previousHexValues[hex.properties.id] = previousHexValues[hex.properties.id] || {};
              previousHexValues[hex.properties.id][property] = currentValue;
            }
          });
        });
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

  function openJSONEditor() {
    if (selectedHexData) {
      toggleGamePause(); // Pause while we edit
      // TODO don't let us click on another tile
  
      // Get the tile value with all historical properties
      const ogHexWithID = hexagonData.features.find((hex) => hex.properties.id == selectedHexData.properties.id)

      editor.setValue(JSON.stringify(ogHexWithID, null, 2), -1);
      document.getElementById("hexInfo").style.display = "none";
      document.getElementById("json-editor-container").style.display = "block";
    }
  }

  function saveJSON() {
    try {
      const newHexData = JSON.parse(editor.getValue());

      console.log(newHexData);

      const indexToReplace = hexagonData.features.findIndex((hex) => hex.properties.id == selectedHexData.properties.id)      
  
      hexagonData.features[indexToReplace] = newHexData

      document.getElementById("json-editor-container").style.display = "none";
      document.getElementById("hexInfo").style.display = "block";
  
      alert("File saved successfully at " + hexDataURI);
    } catch (error) {
      alert("Invalid JSON. Please check your input and try again.");
    }
  }

  function cancelJSON() {
    document.getElementById("json-editor-container").style.display = "none";
    document.getElementById("hexInfo").style.display = "block";
  }
  
});



