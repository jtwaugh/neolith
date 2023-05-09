import json
import os
from django.conf import settings

def load_hexagon_data():
    data_file = os.path.join(settings.BASE_DIR, 'game', 'static/game/assets/', 'combined_map.geojson')
    with open(data_file, 'r') as file:
        hexagon_data = json.load(file)
    return hexagon_data


def process_hex_updates(hexagon_data):
    properties = ["terrain", "climate", "koeppen", "population_density"]
    previous_hex_values = {}
    hex_updates = {}

    if hexagon_data and "features" in hexagon_data:
        for hex in hexagon_data["features"]:
            for property in properties:
                property_years = list(map(int, hex["properties"][property].keys()))

                for year in property_years:
                    current_value = hex["properties"][property][str(year)]
                    previous_value = previous_hex_values.get(hex["properties"]["id"], {}).get(property)

                    if current_value != previous_value:
                        if year not in hex_updates:
                            hex_updates[year] = {}
                        if hex["properties"]["id"] not in hex_updates[year]:
                            hex_updates[year][hex["properties"]["id"]] = {}

                        hex_updates[year][hex["properties"]["id"]][property] = hex["properties"][property][str(year)]

                        if hex["properties"]["id"] not in previous_hex_values:
                            previous_hex_values[hex["properties"]["id"]] = {}

                        previous_hex_values[hex["properties"]["id"]][property] = current_value

    return hex_updates


def create_current_hexes(hexagon_data, current_year):
    if hexagon_data:
        current_hexes = []
        for hex in hexagon_data["features"]:
            updated_hex_properties = {"id": hex["properties"]["id"]}
            for property in settings.HEX_PROPERTIES:
                property_years = [int(year) for year in hex["properties"][property].keys()]
                valid_years = [year for year in property_years if year <= current_year]
                if valid_years:
                    latest_year = max(valid_years)
                    updated_hex_properties[property] = hex["properties"][property][str(latest_year)]
            new_hex = hex.copy()
            new_hex["properties"] = updated_hex_properties
            current_hexes.append(new_hex)
    return current_hexes

