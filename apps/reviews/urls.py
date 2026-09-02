from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('listing/<uuid:listing_id>/add/', views.add_review, name='add'),
    path('<uuid:review_id>/delete/', views.delete_review, name='delete'),
]
