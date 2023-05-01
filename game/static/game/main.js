document.addEventListener('DOMContentLoaded', () => {
    let settlements = [
        {
          "id": 2,
          "properties": {
            "name": "Çatalhöyük",
            "founding": 7400,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [32.827679, 37.668047]
          },
          "population": {
            "7400": 3000,
            "7300": 3500,
            "7200": 4000,
            "7100": 4500,
            "7000": 5000,
            "6900": 5500
          }
        },
        {
          "id": 3,
          "properties": {
            "name": "Hunter-Gatherer Settlements",
            "founding": 11000,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [36.456382, 40.222036]
          },
          "population": {
            "11000": 80,
            "10900": 85,
            "10800": 90,
            "10700": 95
          }
        },
        {
          "id": 4,
          "properties": {
            "name": "Jericho",
            "founding": 9600,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [35.444362, 31.846850]
          },
          "population": {
            "9600": 2000,
            "9500": 2200,
            "9400": 2300,
            "9300": 2400,
            "9200": 2500,
            "9100": 2600
          }
        },
        {
          "id": 5,
          "properties": {
            "name": "Hunter-Gatherer Settlements",
            "founding": 10600,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [28.709477, 44.872065]
          },
          "population": {
            "10600": 70,
            "10500": 75,
            "10400": 80,
            "10300": 85
          }
        },
        {
          "id": 6,
          "properties": {
            "name": "Göbekli Tepe",
            "founding": 9600,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [38.922547, 37.223300]
          },
          "population": {
            "9600": 300,
            "9500": 350,
            "9400": 400,
            "9300": 450,
            "9200": 500,
            "9100": 550
          }
        },
        {
          "id": 7,
          "properties": {
            "name": "Hunter-Gatherer Settlements",
            "founding": 10200,
            "type": "settlement"
          },
          "geometry": {
            "type": "Point",
            "coordinates": [1.276750, 48.357550]
          },
          "population": {
            "10200": 60
          }
        },
        {
            "id": 8,
            "properties": {
              "name": "Hunter-Gatherer Settlements",
              "founding": 10200,
              "type": "settlement"
            },
            "geometry": {
              "type": "Point",
              "coordinates": [1.276750, 48.357550]
            },
            "population": {
              "10200": 60,
              "10100": 65,
              "10000": 70,
              "9900": 75
            }
        },
        {
            "id": 9,
            "properties": {
                "name": "Ain Ghazal",
                "founding": 7250,
                "type": "settlement"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [35.893529, 31.992472]
            },
            "population": {
                "7250": 1300,
                "7200": 1400,
                "7150": 1500,
                "7100": 1600,
                "7050": 1700,
                "7000": 1800
            }
        },
        {
            "id": 10,
            "properties": {
                "name": "Hunter-Gatherer Settlements",
                "founding": 9800,
                "type": "settlement"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [10.594290, 57.708870]
            },
            "population": {
                "9800": 50,
                "9700": 55,
                "9600": 60,
                "9500": 65
            }
        },
        {
            "id": 11,
            "properties": {
                "name": "Tell Sabi Abyad",
                "founding": 6100,
                "type": "settlement"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [38.702020, 36.536990]
            },
            "population": {
                "6100": 1200,
                "6050": 1250,
                "6000": 1300,
                "5950": 1350,
                "5900": 1400,
                "5850": 1450
            }
        },
        {
            "id": 12,
            "properties": {
              "name": "Hunter-Gatherer Settlements",
              "founding": 9400,
              "type": "settlement"
            },
            "geometry": {
              "type": "Point",
              "coordinates": [-3.703790, 40.416775]
            },
            "population": {
              "9400": 40,
              "9300": 45,
              "9200": 50,
              "9100": 55
            }
        },
        {
            "id": 13,
            "properties": {
                "name": "Beidha",
                "founding": 7000,
                "type": "settlement"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [35.445346, 30.334087]
            },
            "population": {
                "7000": 1100,
                "6950": 1150,
                "6900": 1200,
                "6850": 1250
            }
         }
    ]


    let currentYear = -7500;
    let intervalID;


    // Create a Leaflet map
    const map = L.map('map').setView([39.0742, 21.8243], 4); // Set the center and zoom level

    // Add a basemap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Display information about the clicked hex
    function showHexInfo(feature) {}

    const startScreen = document.getElementById('start-screen');
    const gameScreen = document.getElementById('game-screen');
    const startYearInput = document.getElementById('start-year');
    const startGameButton = document.getElementById('start-game');
    const pausePlayButton = document.getElementById('pause-play');
    const closeInfoButton = document.getElementById('close-info');
    const mapContainer = document.getElementById('map-container');
    const currentYearDisplay = document.getElementById('current-year');
    const settlementInfo = document.getElementById('settlement-info');
    const settlementName = document.getElementById('settlement-name');
    const settlementPopulation = document.getElementById('settlement-population');
    const settlementLayer = L.layerGroup();

    // Load the GeoJSON data
    fetch('/static/game/assets/hex.geojson')
    .then(response => response.json())
    .then(geojsonData => {
        // Add the hex grid to the map
        L.geoJSON(geojsonData, {
        onEachFeature: (feature, layer) => {
            // Attach a click event to each hex
            layer.on('click', (event) => {
            // Call the showHexInfo function and pass the feature object
            showHexInfo(feature);
            
            // Add the following line to stop event propagation, so that click events from underlying layers don't get triggered
            event.stopPropagation();
            });
        },
        }).addTo(map);

        settlementLayer.addTo(map);
    });

    function createSettlement(settlement) {
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
        marker.on('click', () => {
            settlementName.textContent = settlement.properties.name;
            const currentPopulation = settlement.population_history.find(
                entry => entry.year <= currentYear
            );
            settlementPopulation.innerText = `Population: ${currentPopulation.population}`;
            settlementInfo.style.display = 'block';
        });
      }


    function startGame() {
        startScreen.style.display = 'none';
        gameScreen.style.display = 'block';
        currentYear = parseInt(startYearInput.value, 10);
        currentYearDisplay.innerText = currentYear;

        settlements.forEach(settlement => {
            createSettlement(settlement);
        });
        intervalID = setInterval(() => {
            currentYear++;
            currentYearDisplay.innerText = currentYear;
        }, 1000);
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

    startGameButton.addEventListener('click', startGame);
    pausePlayButton.addEventListener('click', toggleGamePause);
    closeInfoButton.addEventListener('click', hideSettlementInfo);
});



