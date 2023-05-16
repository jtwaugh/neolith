import json
import os

from django.conf import settings

import math


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


def process_adjacency_map(hexagon_data):
    adjacency_map = {}

    min_x = min(hex['properties']['left'] for hex in hexagon_data['features'])
    min_y = min(hex['properties']['top'] for hex in hexagon_data['features'])

    sample_hex = hexagon_data['features'][0]
    hex_width = abs(sample_hex['properties']['left'] - sample_hex['properties']['right']) * 3/4
    hex_height = abs(sample_hex['properties']['top'] - sample_hex['properties']['bottom'])

    # Create a dictionary of hexagons indexed by their grid coordinates
    grid_to_hex = {}
    for hex in hexagon_data['features']:
        grid_x = round(((hex['properties']['left'] - min_x) / hex_width))
        y_offset = -hex_height / 2 if grid_x % 2 == 0 else 0
        grid_y = round((((hex['properties']['top'] - min_y) + y_offset) / hex_height))
        grid_to_hex[(grid_x, grid_y)] = hex

    # Determine offsets for adjacent hexes in flat-topped configuration
    x_offsets = [0, 1, 1, 0, -1, -1]
    y_offsets_even_q = [-1, 0, 1, 1, 1, 0]
    y_offsets_odd_q = [-1, -1, 0, 1, 0, -1]

    # Generate adjacency map
    for grid, hex in grid_to_hex.items():
        adjacency_map[hex['properties']['id']] = []
        for i in range(6):
            if grid[0] % 2 == 0:
                adjacent_grid = (grid[0] + x_offsets[i], grid[1] + y_offsets_even_q[i])
            else:
                adjacent_grid = (grid[0] + x_offsets[i], grid[1] + y_offsets_odd_q[i])
            if adjacent_grid in grid_to_hex:
                adjacency_map[hex['properties']['id']].append(grid_to_hex[adjacent_grid]['properties']['id'])

    return adjacency_map
