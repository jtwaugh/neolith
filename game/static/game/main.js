document.addEventListener('DOMContentLoaded', () => {
    let settlements = []

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
      .range([  "#2ca02c", "#184a85", "#ff7f0e", "#d62728"]); // Add corresponding colors for each terrain type

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

    let hexLayer; // GPT doesn't really know what this is supposed to do

    let hexagonData; // Raw data containing hex history, probably containing duplicates that aren't actually updates. TODO remove duplicate values
    let currentHexes; // Hexes starting from current year
    let hexUpdates = {}; // Diffs

    let currentYear = -8000;
    const speedSlider = document.getElementById("speed-slider");
    const yearsPerSecondDisplay = document.getElementById("years-per-second");
    let intervalID;

    speedSlider.addEventListener("input", () => {
      adjustGameSpeed();
    });

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
          const mapModeSelector = L.DomUtil.create('select', 'map-mode-selector', container);
    
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
    

    // Create a Leaflet map
    const map = L.map('map').setView([39.0742, 21.8243], 4); // Set the center and zoom level
    
    const svgLayer = L.svg();
    svgLayer.addTo(map);

    function getHexes() {
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

    function drawHexagons(selectedMode) {
      const selectedColorScheme = colorSchemes[selectedMode];
    
      if (hexLayer) {
        // If hexLayer exists, we remove it from the map and draw a new one with the updated hexes
        map.removeLayer(hexLayer);
      }
    
      hexLayer = L.layerGroup();
    
      // Loop over the hexagons and add them to the layer group
      currentHexes.forEach((hex) => {
        hexLayer.addLayer(L.geoJSON(hex, {
          style: function (feature) {
            return {
              fillColor: selectedColorScheme(feature.properties[selectedMode]),
              weight: 0.3,
              opacity: 1,
              color: 'grey',
              fillOpacity: 1.0
            };
          },
          onEachFeature: function (feature, layer) {
            layer.on({
              click: function() {showHexInfo(feature);}
            });
          }
        }));
      });
    }

    // Update a single hex
    function updateHexStyle(hex) {
      const selectedMode = document.querySelector('.map-mode-selector').value;
      const selectedColorScheme = colorSchemes[selectedMode];
        
      const updatedHex = L.geoJSON(hex, {
        style: function (feature) {
          return {
            fillColor: selectedColorScheme(feature.properties[selectedMode]),
            weight: 0.3,
            opacity: 1,
            color: 'grey',
            fillOpacity: 1.0
          };
        },
        onEachFeature: function (feature, layer) {
          layer.on({
            click: function() {showHexInfo(feature);}
          });
        }
      });
    
      hexLayer.removeLayer(hex);
      hexLayer.addLayer(updatedHex);
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
                updateHexStyle(hex);
              }
            });
          }
        });
      }
    }

    // Display information about the clicked hex
    function showHexInfo(feature) {
      const properties = feature.properties;
      const info = `
        <p>Terrain: ${properties.terrain}</p>
        <p>Climate Code: ${properties.climate}</p>
        <p>Koeppen Index: ${properties.koeppen}</p>
        <p>Resources: ${properties.resources}</p>
        <p>Agriculture Adoption: ${properties.agriculture_adoption}</p>
        <p>Trade Route Quality: ${properties.trade_route_quality}</p>
        <p>Caloric Surplus: ${properties.caloric_surplus}</p>
        <p>People per Square km: ${properties.population_density}</p>
      `;

      const hexInfoElement = document.getElementById("hexInfo");
      hexInfoElement.innerHTML = info;
      hexInfoElement.classList.add("neolithic-style");
    }

    function updateMapMode() {
      const selectedMode = document.querySelector('.map-mode-selector').value;
      // Remove the existing hex layer
      if (hexLayer){
        map.removeLayer(hexLayer);
      }
    
      // Redraw the hexagons with the new color scheme
      if (hexagonData){
        drawHexagons(selectedMode); // Render the hexgons to the hexLayer object
        hexLayer.addTo(map); // Actually add it to the map object
      }
    }

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
    const settlementLayer = L.layerGroup();

    settlementLayer.addTo(map);

    let settlementUpdates = {};

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

    function startGame() {
        startScreen.style.display = 'none';
        gameScreen.style.display = 'block';
        
        currentYear = parseInt(startYearInput.value, 10);
        currentYearDisplay.innerText = currentYear;
        document.getElementById("hexInfo").style.display = "block";

        fetch('/static/game/assets/combined_map.geojson')
        .then(response => response.json())
        .then(data => {
          hexagonData = data;
          prepareHexUpdates(); // Turn hexes into just their updates TODO remove duplicates
          getHexes(); // Set the current values of the hexes
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

    function hideSettlementInfo() {
        settlementInfo.style.display = 'none';
    }

    function createPieChart(data) {
      const width = 200;
      const height = 200;
      const radius = Math.min(width, height) / 2;
    
      const color = d3.scaleOrdinal(d3.schemeCategory10);
    
      const pie = d3.pie().value(d => d.value);
    
      const arc = d3.arc()
        .outerRadius(radius - 10)
        .innerRadius(0);
    
      const svg = d3.create("svg")
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${width / 2},${height / 2})`);
    
      const g = svg.selectAll(".arc")
        .data(pie(data))
        .join("g")
        .attr("class", "arc");
    
      g.append("path")
        .attr("d", arc)
        .style("fill", d => color(d.data.label));
    
      return svg.node();
    }

    function displayPieChart(event, d) {
      // Example genetic breakdown data
      const geneticData = [
        { label: "Gene A", value: 30 },
        { label: "Gene B", value: 50 },
        { label: "Gene C", value: 20 },
      ];
    
      const pieChartDiv = document.createElement("div");
      pieChartDiv.style.position = "absolute";
      pieChartDiv.style.left = `${event.clientX}px`;
      pieChartDiv.style.top = `${event.clientY}px`;
    
      const pieChart = createPieChart(geneticData);
      pieChartDiv.appendChild(pieChart);
    
      document.body.appendChild(pieChartDiv);
    
      // Remove the pie chart when clicking outside
      d3.select(document).on("click", () => {
        pieChartDiv.remove();
      }, { once: true });
    }    
    

    startGameButton.addEventListener('click', startGame);
    pausePlayButton.addEventListener('click', toggleGamePause);
});



