from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.core.cache import cache
from django.conf import settings
import json

from django.http import HttpResponseNotAllowed, Http404

from .hex_processing import process_hex_updates, create_current_hexes, load_hexagon_data, process_adjacency_map

HEX_UPDATES_CACHE_KEY = "hex_updates"
HEXAGON_DATA_CACHE_KEY = "hexagon_data"

HEX_DATA_FILE = "hex_data.json"

def game_view(request):
    context = {
        'hex_properties': settings.HEX_PROPERTIES,
        'color_schemes': settings.COLOR_SCHEMES,
    }
    return render(request, 'game.html', context)

def save_hex_data(request):
    try:
        new_hex_data = json.loads(request.POST.get('hex_data'))
        hex_id = new_hex_data['properties']['id']

        hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
        if not hexagon_data:
            raise ValueError('Hexagon data not found in cache.')

        index_to_replace = next((i for i, hex in enumerate(hexagon_data['features']) if hex['properties']['id'] == hex_id), None)
        if index_to_replace is None:
            raise ValueError(f'Hexagon with ID {hex_id} not found in hexagon data.')

        hexagon_data['features'][index_to_replace] = new_hex_data
        cache.set(HEXAGON_DATA_CACHE_KEY, hexagon_data)

        response = HttpResponse(content_type='application/json')
        response.content = json.dumps({'success': True})
        return response
    except Exception as e:
        response = HttpResponseBadRequest(content_type='application/json')
        response.content = json.dumps({'success': False, 'message': str(e)})
        return response


def read_hex_data_from_file_and_cache(request):
    if not cache.get(HEXAGON_DATA_CACHE_KEY):
        hexagon_data = load_hexagon_data()

        if not hexagon_data:
            return JsonResponse(
            {
                "success": False,
                "message": "Hexagon data not cached successfully"
            }
        )

        cache.set(HEXAGON_DATA_CACHE_KEY, hexagon_data)
        return JsonResponse(
            {
                "success": True,
                "message": "Hexagon data cached successfully"
            }
        )
    else:
        return JsonResponse(
            {
                "success": True,
                "message": "Hexagon data already cached"
            }
        )


def prepare_hex_updates(request):
    hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
    if not hexagon_data:
        return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")
        
    hex_updates = process_hex_updates(hexagon_data)
    cache.set(HEX_UPDATES_CACHE_KEY, hex_updates)
    return JsonResponse(hex_updates)

# NOTE years in BCE
def get_current_hexes(request, current_year):
    if request.method == 'GET':
        hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
        if not hexagon_data:
            return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")

        current_hexes = create_current_hexes(hexagon_data, -1 * current_year)
        return JsonResponse(current_hexes, safe=False)
    else: 
        return HttpResponseNotAllowed(['GET'])

def get_hex_updates(request, year):
    if request.method == 'GET':
        hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
        if not hexagon_data:
            return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")

        hex_updates = cache.get(HEX_UPDATES_CACHE_KEY)
        updates = hex_updates.get(year, {}) if hex_updates else {}
        return JsonResponse(updates)
    else: 
        return HttpResponseNotAllowed(['GET'])

# NOTE years in BCE
def get_hex_updates_range(request, start_year, end_year):
    if request.method == 'GET':
        hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
        if not hexagon_data:
            raise Http404("Hexagon data not cached. Call cache_hexagon_data first.")

        hex_updates = cache.get(HEX_UPDATES_CACHE_KEY)
        if not hex_updates:
            return HttpResponseBadRequest("Hexagon updates not cached. Call prepare_hex_updates first.")

        updates = {}
        for year in range(-1 * start_year, -1 * end_year):
            updates[year] = hex_updates.get(year, {})
        return JsonResponse(updates)
    else: 
        return HttpResponseNotAllowed(['GET'])

# Retrieve all hexagon data
def get_hexagon_data(request):
    hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
    if not hexagon_data:
        # Load the hexagon data and cache it
        hexagon_data = load_hexagon_data()
        cache.set(HEXAGON_DATA_CACHE_KEY, hexagon_data)

    return JsonResponse(hexagon_data, safe=False)

# Get individual hex
def get_hex_by_id(request, hex_id):
    hexagon_data = cache.get('hexagon_data')
    if not hexagon_data:
        return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")
    for hex in hexagon_data['features']:
        if hex['properties']['id'] == hex_id:
            return JsonResponse(hex)
        
    return JsonResponse({'error': 'Hexagon data not found for id: {}'.format(hex_id)})


@csrf_exempt
def update_hex_by_id(request, hex_id):
    if request.method == 'POST':
        hex_data = json.loads(request.body)
        hex_data['properties']['id'] = hex_id
        hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
        if not hexagon_data:
            return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")

        index_to_replace = next((i for i, hex in enumerate(hexagon_data['features']) if hex['properties']['id'] == hex_id), None)
        if index_to_replace is not None:
            hexagon_data['features'][index_to_replace] = hex_data
            cache.set(HEXAGON_DATA_CACHE_KEY, hexagon_data)
            return HttpResponse("Hex data updated successfully")
        else:
            return HttpResponseBadRequest("Hex data not found")
    else:
        return HttpResponseNotAllowed(['POST'])


def generate_adjacency_map(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    hexagon_data = cache.get(HEXAGON_DATA_CACHE_KEY)
    if not hexagon_data:
        return HttpResponseBadRequest("Hexagon data not cached. Call cache_hexagon_data first.")
    
    adjacency_map = process_adjacency_map(hexagon_data)
    
    return JsonResponse(adjacency_map)
