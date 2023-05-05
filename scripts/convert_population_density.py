import json

# Define your dictionary for population density index lookups
your_dictionary = {
    0.0: 0.0,
    23.0: 0.0,
    31.0: 0.0,
    39.0: 0.0,
    63.0: 0.0,
    127.0: 0.1,
    151.0: 0.3,
    175.0: 0.5,
    183.0: 0.8,
    199.0: 1.5,
    215.0: 1.0,
    231.0: 2.0,
    247.0: 5.0,
}

# Load the GeoJSON file
with open("game/static/game/assets/hex_pop.geojson", "r") as file:
    geojson_data = json.load(file)

# Add the "population_density" feature using the lookup dictionary
for feature in geojson_data["features"]:
    population_density_index = feature["properties"]["population_density_index"]
    population_density = your_dictionary.get(population_density_index, "Unknown")
    feature["properties"]["population_density"] = population_density

# Save the modified GeoJSON data to a new file
with open("game/static/game/assets/hex_pop.geojson", "w") as file:
    json.dump(geojson_data, file, indent=2)
