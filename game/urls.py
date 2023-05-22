from django.urls import path
from . import views

urlpatterns = [
    path('', views.game_view, name='game_view'),
    path('cache_hexagon_data/', views.read_hex_data_from_file_and_cache, name='cache_hexagon_data'),
    path('prepare_hex_updates/', views.prepare_hex_updates, name='prepare_hex_updates'),
    path('get_current_hexes/<int:current_year>/', views.get_current_hexes, name='get_current_hexes'),
    path('get_hex_updates/<int:year>/', views.get_hex_updates, name='get_hex_updates'),
    path('get_hex_updates_range/<int:start_year>/<int:end_year>/', views.get_hex_updates_range, name='get_hex_updates_range'),
    path('get_hexagon_data/', views.get_hexagon_data, name='get_hexagon_data'),
    path('get_hex_by_id/<int:hex_id>/', views.get_hex_by_id, name='get_hex_by_id'),
    path('update_hex_by_id/<int:hex_id>/', views.update_hex_by_id, name='update_hex_by_id'),
    path('generate_adjacency_map/', views.generate_adjacency_map, name='generate_adjacency_map'),
]
