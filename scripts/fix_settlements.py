import json

# Load the GeoJSON file
with open("game/static/game/assets/settlements.json", "r") as file:
    json_data = json.load(file)

def reformat_settlement(settlement):
    settlement["properties"]["population"] = settlement.pop("population")
    return settlement


geojson_data = [reformat_settlement(settlement) for settlement in json_data]

with open("game/static/game/assets/settlements.geojson", "w") as geo_file:
    json.dump(geojson_data, geo_file, indent=2)

