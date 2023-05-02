import json
import random

# Load the GeoJSON file
with open("game/static/game/assets/hex.geojson", "r") as file:
    geojson_data = json.load(file)

# List of possible resources, major terrain features, and Köppen climate types
resources_list = ["Wood", "Berries", "Fish", "Stone", "Copper", "Deer"]
terrain_list = ["Forest", "Plains", "Desert", "Mountain", "Hills", "Swamp"]
climate_list = ["Af", "Am", "Aw", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb", "Cwc", "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa", "Dfb", "Dfc", "Dfd", "ET", "EF"]

# Update GeoJSON features with random values
for feature in geojson_data["features"]:
    feature["properties"]["resources"] = random.sample(resources_list, k=3)
    feature["properties"]["terrain"] = random.choice(terrain_list)
    feature["properties"]["climate"] = random.choice(climate_list)

# Save the updated GeoJSON file
with open("game/static/game/assets/hex.geojson", "w") as file:
    json.dump(geojson_data, file, indent=2)
