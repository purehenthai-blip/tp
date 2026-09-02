from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('',                            views.order_list,         name='list'),
    path('<uuid:order_id>/',             views.order_detail,       name='detail'),
    path('checkout/<uuid:listing_id>/',  views.checkout,           name='checkout'),
    path('<uuid:order_id>/verify/',      views.verify_delivery,    name='verify'),
    path('<uuid:order_id>/dispute/',     views.open_dispute,       name='dispute'),
    path('<uuid:order_id>/release/',     views.vendor_release_item, name='release'),
]
