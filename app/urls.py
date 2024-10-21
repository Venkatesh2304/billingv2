from . import views,admin
from .admin import admin_site
from django.urls import path
from .views import manual_print_view,basepack
from django.views.decorators.cache import cache_page

urlpatterns = [
    # path('billautocomplete/', BillAutocomplete.as_view(), name='billautocomplete'),
    path('manual_print/', manual_print_view , name='manual-print'),
    # path('get-outstanding/<str:inum>/', get_outstanding, name='get-outstanding'),
    # path('get-outstanding-report', get_outstanding_report, name='get-outstanding-report'),
    path('party-sync', basepack, name='basepack'),
    path('jsi18n/', cache_page(3600)(admin_site.i18n_javascript), name='javascript-catalog'),
    path('', admin_site.urls) ,
]