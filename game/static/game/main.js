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

    let tech_tree = technology_tree = {
      "basic_tools": {
          "dependencies": [],
          "unlocks": ["agriculture", "basic_pottery", "basic_hunting"],
      },
      "basic_pottery": {
          "dependencies": ["basic_tools"],
          "unlocks": [
              "Cardium pottery",
              "Linear pottery",
              "Vinča pottery",
              "Funnel beaker pottery",
              "Cucuteni-Trypillia pottery",
              "Yamnaya pottery",
          ],
      },
      "agriculture": {
          "dependencies": ["basic_tools"],
          "unlocks": ["animal_husbandry", "irrigation", "plant_domestication"],
      },
      "animal_husbandry": {
          "dependencies": ["agriculture"],
          "unlocks": ["pastoralism", "horse_domestication"],
      },
      "basic_hunting": {
          "dependencies": ["basic_tools"],
          "unlocks": ["marine_resources"],
      },
      "plant_domestication": {
          "dependencies": ["agriculture"],
          "unlocks": [],
      },
      "irrigation": {
          "dependencies": ["agriculture"],
          "unlocks": ["advanced_agriculture"],
      },
      "pastoralism": {
          "dependencies": ["animal_husbandry"],
          "unlocks": [],
      },
      "horse_domestication": {
          "dependencies": ["animal_husbandry"],
          "unlocks": ["wheeled_vehicles"],
      },
      "advanced_agriculture": {
          "dependencies": ["irrigation"],
          "unlocks": ["large_settlements"],
      },
      "marine_resources": {
          "dependencies": ["basic_hunting"],
          "unlocks": [],
      },
      "large_settlements": {
          "dependencies": ["advanced_agriculture"],
          "unlocks": ["megalithic_tombs", "amber_trade"],
      },
      "wheeled_vehicles": {
          "dependencies": ["horse_domestication"],
          "unlocks": [],
      },
      "megalithic_tombs": {
          "dependencies": ["large_settlements"],
          "unlocks": [],
      },
      "amber_trade": {
          "dependencies": ["large_settlements"],
          "unlocks": [],
      },
      "metallurgy": {
          "dependencies": ["basic_tools"],
          "unlocks": ["copper_working"],
      },
      "copper_working": {
          "dependencies": ["metallurgy"],
          "unlocks": [],
      },
    }

    let gene_pools = ["WHG", "EEF", "EHG", "CHG", "ANF", "SP"]

    let neolithic_cultures = [
      {
          "name": "Cardium Pottery Culture",
          "gene_pool": {"EEF": 0.9, "WHG": 0.1},
          "material_practices": [
              "Cardium pottery",
              "agriculture",
              "animal husbandry",
              "marine resources",
          ],
      },
      {
          "name": "Linear Pottery Culture (LBK)",
          "gene_pool": {"EEF": 0.95, "WHG": 0.05},
          "material_practices": [
              "Linear pottery",
              "agriculture",
              "animal husbandry",
              "longhouses",
          ],
      },
      {
          "name": "Vinča Culture",
          "gene_pool": {"EEF": 0.9, "ANF": 0.1},
          "material_practices": [
              "Vinča pottery",
              "agriculture",
              "animal husbandry",
              "metallurgy (copper)",
              "large settlements",
          ],
      },
      {
          "name": "Funnel Beaker Culture (TRB)",
          "gene_pool": {"EEF": 0.6, "WHG": 0.3, "EHG": 0.1},
          "material_practices": [
              "Funnel beaker pottery",
              "agriculture",
              "animal husbandry",
              "megalithic tombs",
              "amber trade",
          ],
      },
      {
          "name": "Cucuteni-Trypillia Culture",
          "gene_pool": {"EEF": 0.7, "WHG": 0.2, "CHG": 0.1},
          "material_practices": [
              "Cucuteni-Trypillia pottery",
              "agriculture",
              "animal husbandry",
              "large settlements",
              "painted ceramics",
          ],
      },
      {
          "name": "Yamnaya Culture",
          "gene_pool": {"EHG": 0.4, "CHG": 0.4, "SP": 0.2},
          "material_practices": [
              "Yamnaya pottery",
              "pastoralism",
              "horse domestication",
              "kurgan burial mounds",
              "wheeled vehicles",
          ],
      },
    ]  

    const terrainColors = d3.scaleOrdinal()
      .domain(list(range(31))) // Add as many terrain types as you have
      .range(
        [
          "#ffffff", 
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
          "83ff48", 
          "54ce00", 
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

    let currentYear = -7500;
    let intervalID;

    // Create a Leaflet map
    const map = L.map('map').setView([39.0742, 21.8243], 4); // Set the center and zoom level
    
    const svgLayer = L.svg();
    svgLayer.addTo(map);
    
    function drawHexagons(data) {
      console.log(data)
      const hexLayer = L.geoJSON(data, {
        style: function (feature) {
          return {
            fillColor: terrainColors(int(feature.properties.koeppen)),
            weight: 1,
            opacity: 1,
            color: 'white',
            fillOpacity: 0.7
          };
        },
        onEachFeature: function (feature, layer) {
          layer.on({
            click: function() {showHexInfo(feature);}
          });
        }
      }).addTo(map);
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
        <p>Population: ${properties.population}</p>
      `;
      document.getElementById("hexInfo").innerHTML = info;
    }

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

    settlementLayer.addTo(map);

    fetch('/static/game/assets/hex.geojson')
    .then(response => response.json())
    .then(data => {
      // Call the drawHexagons function with the fetched GeoJSON data
      drawHexagons(data);
    })
    .catch(error => console.error('Error fetching GeoJSON data:', error));

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
    closeInfoButton.addEventListener('click', hideSettlementInfo);
});



