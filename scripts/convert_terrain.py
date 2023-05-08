import json
import os

# Define your dictionary for population density index lookups
# Key is (r, g, b)
qgis_to_terrain_name = {
    (255.0, 0.0, 0.0): "Chaparral",
    (255.0, 0.0, 255.0): "Extreme Desert",
    (0.0, 0.0, 255.0): "Semi-Desert",
    (0.0, 255.0, 255.0): "Ice",
    (0.0, 255.0, 0.0): "Free",
    (255.0, 255.0, 0.0): "Savannah",
    (127.0, 0.0, 0.0): "Woodlands",
    (127.0, 0.0, 127.0): "Mountains",
    (0.0, 0.0, 127.0): "Tropical Forest",
    (0.0, 127.0, 127.0): "Grassland",
    (0.0, 127.0, 0.0): "Temperate Forest",
    (130.0, 127.0, 0.0): "Steppe-Forest",
    (102.0, 102.0, 102.0): "Boreal Forest",
    (178.0, 178.0, 178.0): "Land",
    (51.0, 51.0, 51.0): "Water",
}

# Load the GeoJSON file

input_folder = "game/static/game/assets/maps/"
map_files = ["9000_bce.geojson", "8000_bce.geojson", "7000_bce.geojson", "6000_bce.geojson", "5000_bce.geojson"]

for mf in map_files:
    with open(os.path.join(input_folder, mf), "r") as file:
        geojson_data = json.load(file)

    # Add the "population_density" feature using the lookup dictionary
    for feature in geojson_data["features"]:
        terrain_index = (feature["properties"]["red_majority"], feature["properties"]["green_majority"], feature["properties"]["blue_majority"])
        terrain = qgis_to_terrain_name.get(terrain_index, "Unknown")
        if terrain == "Unknown":
            print(terrain_index)
        feature["properties"]["terrain"] = terrain

    # Save the modified GeoJSON data to a new file
    with open(os.path.join(input_folder, mf), "w") as file:
        json.dump(geojson_data, file, indent=2)
