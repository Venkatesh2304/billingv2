from . import views,admin
from .admin import admin_site
from django.urls import path
from .views import manual_print_view,basepack,get_bill_data,scan_bills
from django.views.decorators.cache import cache_page

urlpatterns = [
    # path('billautocomplete/', BillAutocomplete.as_view(), name='billautocomplete'),
    path('manual_print/', manual_print_view , name='manual-print'),
    path('get_bill_data/<str:inum>/<str:vehicle>/', get_bill_data, name='get_bill_data'),
    path('scan_bills/', scan_bills, name='scan_bills'),
    path('party-sync', basepack, name='basepack'),
    path('jsi18n/', cache_page(3600)(admin_site.i18n_javascript), name='javascript-catalog'),
    path('', admin_site.urls) ,
]