from . import views,admin
from .admin import admin_site
from django.urls import path
from .views import manual_print_view,basepack,get_bill_data,scan_bills,reload_server_view
from .views import get_party_outstanding,salesman_cheque_entry_view,add_salesman_cheque,get_bill_out,get_bill_in
from .views import ScanPendingBills,sync_impact
from django.views.decorators.cache import cache_page

urlpatterns = [
    # path('billautocomplete/', BillAutocomplete.as_view(), name='billautocomplete'),
    path('reload_server/', reload_server_view , name='reload_server'),
    path('manual_print/', manual_print_view , name='manual-print'),
    path('get_bill_data/', get_bill_data, name='get_bill_data'),
    path('get_party_outstanding/', get_party_outstanding, name='get_party_outstanding'),
    path('salesman_cheque/', salesman_cheque_entry_view, name='salesman_cheque'),
    path('add_salesman_cheque', add_salesman_cheque, name='add_salesman_cheque'),
    path('scan_bills', scan_bills, name='scan_bills'),
    path('scan_pending_bills', ScanPendingBills.as_view() , name='scan_pending_bills'),
    path('sync_impact', sync_impact, name='sync_impact'),
    # path('vehicle_selection', vehicle_selection, name='vehicle_selection'),
    path('get_bill_out', get_bill_out, name='get_bill_out'),
    path('get_bill_in', get_bill_in, name='get_bill_in'),
    path('party-sync', basepack, name='basepack'),
    path('jsi18n/', cache_page(3600)(admin_site.i18n_javascript), name='javascript-catalog'),
    path('', admin_site.urls) ,
]