from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

def game_view(request):
    return render(request, 'game.html')
