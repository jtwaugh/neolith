import json
import os

# Define your dictionary for population density index lookups
your_dictionary = {
    51.0: "Water",
    178.0: "Plains",
    127.0: "Mountains",
}

# Load the GeoJSON file

input_folder = "game/static/game/assets/maps/"
map_files = ["6000_bce.geojson", "5000_bce.geojson"]

for mf in map_files:
    with open(os.path.join(input_folder, mf), "r") as file:
        geojson_data = json.load(file)

    # Add the "population_density" feature using the lookup dictionary
    for feature in geojson_data["features"]:
        terrain_index = feature["properties"]["terrain"]
        population_density = your_dictionary.get(terrain_index, "Unknown")
        feature["properties"]["terrain"] = population_density

    # Save the modified GeoJSON data to a new file
    with open(os.path.join(input_folder, mf), "w") as file:
        json.dump(geojson_data, file, indent=2)
