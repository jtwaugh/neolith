import json

# Load the GeoJSON file
with open("game/static/game/assets/hex_pop.geojson", "r") as file:
    geojson_data = json.load(file)

# Extract unique values for 'population_density_index'
unique_population_density_indices = set()

for feature in geojson_data["features"]:
    population_density_index = feature["properties"]["population_density_index"]
    unique_population_density_indices.add(population_density_index)

# Print the unique population density indices
print("Unique population density indices:")
for index in sorted(unique_population_density_indices):
    print(index)
