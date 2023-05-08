import json

koeppen_key = {
    0.0: "Ocean",
    1.0: "Af",
    2.0: "Am",
    3.0: "Aw/As",
    4.0: "BWh",
    5.0: "BWk",
    6.0: "BSh",
    7.0: "BSk",
    8.0: "Csa",
    9.0: "Csb",
    10.0: "Csc",
    11.0: "Cwa",
    12.0: "Cwb",
    13.0: "Cwc",
    14.0: "Cfa",
    15.0: "Cfb",
    16.0: "Cfc",
    17.0: "Dsa",
    18.0: "Dsb",
    19.0: "Dsc",
    20.0: "Dsd",
    21.0: "Dwa",
    22.0: "Dwb",
    23.0: "Dwc",
    24.0: "Dwd",
    25.0: "Dfa",
    26.0: "Dfb",
    27.0: "Dfc",
    28.0: "Dfd",
    29.0: "ET",
    30.0: "EF",
    31.0: "missingno",
}

# Load the GeoJSON file
with open("game/static/game/assets/hex_pop.geojson", "r") as file:
    geojson_data = json.load(file)

# Add the "population_density" feature using the lookup dictionary
for feature in geojson_data["features"]:
    koeppen = feature["properties"]["koeppen"]
    if koeppen < 0.00001:
        feature["properties"]["terrain"] = 0
    else:
        feature["properties"]["terrain"] = 1
    feature["properties"]["climate"] = koeppen_key[koeppen]

# Save the modified GeoJSON data to a new file
with open("game/static/game/assets/maps/5000_bce.geojson", "w") as file:
    json.dump(geojson_data, file, indent=2)
