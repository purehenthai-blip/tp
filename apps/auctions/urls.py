from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    path('', views.auction_list, name='list'),
    path('<uuid:auction_id>/', views.auction_detail, name='detail'),
    path('<uuid:auction_id>/bid/', views.place_bid_view, name='bid'),
]
