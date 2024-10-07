from . import views,admin
from .admin import admin_site
from django.urls import path
from .views import BillAutocomplete,get_outstanding,get_outstanding_report, manual_print_view,basepack

urlpatterns = [
    path('billautocomplete/', BillAutocomplete.as_view(), name='billautocomplete'),
    path('manual_print/', manual_print_view , name='manual-print'),
    path('get-outstanding/<str:inum>/', get_outstanding, name='get-outstanding'),
    path('get-outstanding-report', get_outstanding_report, name='get-outstanding-report'),
    path('party-sync', basepack, name='basepack'),
    path('', admin_site.urls) ,
]