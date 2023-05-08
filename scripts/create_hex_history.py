import json
import os

input_folder = "game/static/game/assets/maps/"
output_folder = "game/static/game/assets/"

properties = ["terrain", "climate", "koeppen", "population_density"]

map_files = ["10000_bce.geojson", "9000_bce.geojson", "8000_bce.geojson", "7000_bce.geojson", "6000_bce.geojson", "5000_bce.geojson", "4000_bce.geojson", "3000_bce.geojson"]
output_file = 'combined_map.geojson'

combined_hexes = {}

for map_file in map_files:
    with open(os.path.join(input_folder, map_file), 'r') as f:
        hex_map = json.load(f)
        print(map_file)
        year = int("-" + map_file.split('_')[0].split('.')[0])
        
        for hex_feature in hex_map['features']:
            hex_id = hex_feature['properties']['id']
            hex_left = hex_feature['properties']['left']
            hex_top = hex_feature['properties']['top']
            hex_bottom = hex_feature['properties']['bottom']
            hex_right = hex_feature['properties']['right']

            if hex_id not in combined_hexes:
                combined_hexes[hex_id] = {
                    'type': 'Feature',
                    'geometry': hex_feature['geometry'],
                    'properties': {
                        'id': hex_id,
                        'left': hex_left,
                        'top': hex_top,
                        'bottom': hex_bottom,
                        'right': hex_right,
                    }
                }

            for property_type in properties:
                hex_property = hex_feature['properties'][property_type]

                if property_type not in combined_hexes[hex_id]['properties']:
                    combined_hexes[hex_id]['properties'][property_type] = {}
                combined_hexes[hex_id]['properties'][property_type][year] = hex_property

output_geojson = {
    'type': 'FeatureCollection',
    'features': list(combined_hexes.values())
}

with open(os.path.join(output_folder, output_file), 'w') as f:
    json.dump(output_geojson, f)
