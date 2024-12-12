import base64
from collections import Counter, defaultdict
from collections import abc
import datetime
from functools import partial, update_wrapper
import functools
from io import BytesIO
import json
import shutil
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import custom.secondarybills  as secondarybills
from dal import autocomplete
import logging
import multiprocessing
import os
import re
import shutil
from threading import Thread
import threading
import django
from django.contrib.admin.views.main import ChangeList
import time
import traceback
from typing import Any, Dict, Optional, Type
from django import forms
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.handlers.wsgi import WSGIRequest
from django.db.models.base import Model
from django.db.models.query import QuerySet
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.http.request import HttpRequest
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls.resolvers import URLPattern
import numpy as np
from openpyxl import load_workbook
import pandas as pd
from enum import Enum, IntEnum
from app.common import both_insert, bulk_raw_insert, query_db
import app.models as models 
from django.utils.html import format_html
from django.contrib.admin.templatetags.admin_list import register , result_list  
from django.contrib.admin.templatetags.base import InclusionAdminNode
from custom.Session import Logger  
from typing import Callable
from custom.classes import Billing,IkeaDownloader,Einvoice
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Max,F,Subquery,OuterRef,Q,Min,Sum,Count
from collections import namedtuple
from app.sales_import import AdjustmentInsert, BeatInsert, CollectionInsert, PartyInsert, SalesInsert
from django.urls import path, reverse, reverse_lazy
from django.contrib import messages
import dal.autocomplete
from pytz import timezone
from custom.Session import client
import app.pdf_create as pdf_create
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from rangefilter.filters import NumericRangeFilter
import os 
from requests.exceptions import JSONDecodeError
from django.http import JsonResponse
from urllib.parse import quote, unquote
# from django_admin_multi_selecfrom django.db.models.functions import Concat
from django.db.models import CharField, Value
from django.db.models.functions import Concat


class PrintType(Enum):
    FIRST_COPY = "first_copy"
    DOUBLE_FIRST_COPY = "double_first_copy"
    SECOND_COPY = "second_copy"
    LOADING_SHEET = "loading_sheet"
    LOADING_SHEET_SALESMAN = "loading_sheet_salesman"

import app.aztec as aztec 

def reload_server() : 
    current_time = time.time()
    os.utime("billingv2/settings.py", (current_time, current_time))

os.makedirs("bills/",exist_ok=True)
os.makedirs("voice_notes/",exist_ok=True)

def user_permission(s,*a,**kw) : 
    if a and False : return False #or "add" in a[0] "change" in a[0] or ("add" in a[0] ) 
    return True

class AccessUser(object):
    has_module_perms = has_perm = __getattr__ = user_permission


def submit_button(text) : 
    return forms.CharField(required=False,label="",initial=text,widget=forms.TextInput(attrs={'type' : 'submit'}))

def bold(function) : 
    def wrapper(*args,**kwargs) : 
        return format_html("<b>{}</b>",function(*args,**kwargs))
    update_wrapper(wrapper, function)
    return wrapper

def hyperlink(url,text,new_tab=True,style = "") :  
    if new_tab :  return format_html("<a href='{}' style='{}' target='_blank'>{}</a>",url, style,text)
    else : return format_html("<a href='{}' style='{}'>{}</a>",url, style,text)

def render_confirmation_page(template_name,request,queryset,extra_context = {}) :
     return render(request,template_name, context={'post_data': {key: request.POST.getlist(key) for key in request.POST} , 
                                                "queryset" : queryset, "show_objects" : False , "show_cancel_btn" : False } | extra_context )

@register.tag(name="custom_result_list")
def result_list_tag(parser, token):
    ##Custom result display for given results (used in billing statistics)
    return  InclusionAdminNode(
        parser,
        token,
        func=result_list,
        template_name="custom_result_list.html",
        takes_context=False,
    )

def create_simple_admin_list_filter(title_name,paramter,lookups: dict[str,Callable] = {},allow_all = True) :

    class CustomListFilter(admin.SimpleListFilter) : #admin.SimpleListFilter):
        title = title_name
        parameter_name = paramter
        
        def lookups(self, request, model_admin) -> list[tuple[str, str]]:
            return list(zip(lookups.keys(),lookups.keys()))

        def queryset(self, request, queryset):
            for lookup,queryset_filter in lookups.items() : 
                if lookup == self.value() : 
                    return queryset_filter(queryset)
            return queryset

        # def choices(self, changelist):
        #     add_facets = changelist.add_facets
        #     facet_counts = self.get_facet_queryset(changelist) if add_facets else None
        #     if allow_all : 
        #         yield {
        #         "selected": self.value() is None,
        #         "query_string": changelist.get_query_string(remove=[self.parameter_name]),
        #         "display": _("All"),
        #         }
        #     for i, (lookup, title) in enumerate(self.lookup_choices):
        #         if add_facets:
        #             if (count := facet_counts.get(f"{i}__c", -1)) != -1:
        #                 title = f"{title} ({count})"
        #             else:
        #                 title = f"{title} (-)"
        #         yield {
        #             "selected": self.value() == str(lookup),
        #             "query_string": changelist.get_query_string(
        #                 {self.parameter_name: lookup}
        #             ),
        #             "display": title,
        #         }
                
    return CustomListFilter   


START_DATE = datetime.date(2024,4,1)

def check_last_sync(type,limit) :
    if limit is None : return False 
    last_synced = models.Sync.objects.filter( process = type.capitalize() ).first()
    if last_synced : 
        if isinstance(limit,int) :  
            if (datetime.datetime.now() - last_synced.time).seconds <= limit : return True
        elif isinstance(limit,datetime.date) : 
            if last_synced.time.date() >= limit : return True
        elif isinstance(limit,datetime.datetime):  
            if last_synced.time >= limit : return True
        else : 
            raise Exception(f"Limit specified for {type} = {limit} is not an instance of int,datetime.date or datetime.datetime")
    return False 

def sync_reports(billing = None,limits = {},min_days_to_sync = {}) -> bool :
    min_days_to_sync = defaultdict(lambda : 2 , min_days_to_sync )
    get_sync_from_date_for_model = lambda model_class : max(min( model_class.objects.aggregate(date = Max("date"))["date"] or START_DATE ,
                                                    datetime.date.today() - datetime.timedelta(days=min_days_to_sync[model_class.__name__.lower()]) ), START_DATE)
    
    DeleteType = Enum("DeleteType","datewise all none")
    FunctionTuple = namedtuple("function_tuple",["download_function","model","insert_function","has_date_arg","delete_type"])
    function_mappings = { "sales" : FunctionTuple(Billing.sales_reg,models.Sales,SalesInsert,has_date_arg=True,delete_type=DeleteType.datewise) , 
                          "adjustment" : FunctionTuple(Billing.crnote,models.Adjustment,AdjustmentInsert,has_date_arg=True,delete_type=DeleteType.datewise) , 
                          "collection" : FunctionTuple(Billing.collection,models.Collection,CollectionInsert,has_date_arg=True,delete_type=DeleteType.datewise) , 
                          "party" : FunctionTuple(Billing.party_master,None,PartyInsert,has_date_arg=False,delete_type=DeleteType.none) , 
                          "beat" : FunctionTuple(Billing.get_plg_maps,models.Beat,BeatInsert,has_date_arg=False,delete_type=DeleteType.all) , 
                        }
    
    insert_types_to_update = []
    for insert_type,limit in limits.items() : 
        if insert_type not in function_mappings : raise Exception(f"{insert_type} is not a valid Insert type")
        if not check_last_sync(insert_type,limit) : insert_types_to_update.append(insert_type)

    if len(insert_types_to_update) == 0 : return False 
    if billing is None : billing = Billing()
    with ThreadPoolExecutor() as executor:
        futures = []
        for insert_type in insert_types_to_update : 
            functions = function_mappings[insert_type]
            if functions.has_date_arg : 
                last_updated_date = get_sync_from_date_for_model(functions.model)
                futures.append( executor.submit(functions.download_function, billing, last_updated_date, datetime.date.today()) )
            else : ## No date argument required 
                futures.append( executor.submit(functions.download_function, billing) )

        for insert_type,future in zip(insert_types_to_update,futures) :
            functions = function_mappings[insert_type]
            df = future.result()

            if functions.delete_type == DeleteType.datewise : 
                last_updated_date = get_sync_from_date_for_model(functions.model)
                functions.model.objects.filter(date__gte = last_updated_date).delete()
            elif functions.delete_type == DeleteType.all : 
                functions.model.objects.all().delete()
            elif functions.delete_type == DeleteType.none : 
                pass 
            else : 
                raise Exception(f"{functions.delete_type} is not a valid delete type")

            functions.insert_function(df)
            models.Sync.objects.update_or_create( process = insert_type.capitalize() , defaults={"time" : datetime.datetime.now()})
    return True 

            
BillingStatus = IntEnum("BillingStatus",(("NotStarted",0),("Success",1),("Started",2),("Failed",3)))

billing_process_names = ["SYNC" , "PREVBILLS" , "RELEASELOCK" , "COLLECTION", "ORDER"  , "DELIVERY", "REPORTS"  , "DOWNLOAD" , "PRINT" ][:-2]
billing_lock = threading.Lock()

def run_billing_process(billing_log: models.Billing,billing_form : forms.Form) :

    ##Calculate the neccesary values for the billing
    today = datetime.date.today()
    max_lines = billing_form.cleaned_data["max_lines"]    
    order_date =  billing_log.date

    prev_order_total_values = { order.order_no : order.bill_value() for order in models.Orders.objects.filter(date = order_date) } # type: ignore
    today_last_billing_qs = models.Billing.objects.filter(start_time__gte = today, date = order_date).order_by("-start_time")
    last_billing_orders = models.Orders.objects.filter(billing = today_last_billing_qs[1]) if today_last_billing_qs.count() > 1 else models.Orders.objects.none()
    delete_order_nos = [ order.order_no for order in last_billing_orders.filter(delete = True).all() ]
    forced_order_nos = [ order.order_no for order in last_billing_orders.filter(force_order = True).all() ]
    creditrelease = list(last_billing_orders.filter(release = True,delete=False,creditlock=True))
    creditrelease = pd.DataFrame([ [order.party_id , order.party_id , order.party.hul_code ,order.beat.plg.replace('+','%2B')] for order in creditrelease ] , # type: ignore
                                    columns=["partyCode","parCodeRef","parHllCode","showPLG"])
    creditrelease = creditrelease.groupby(["partyCode","parCodeRef","parHllCode","showPLG"]).size().reset_index(name='increase_count') # type: ignore
    creditrelease = creditrelease.to_dict(orient="records")

    def filter_orders_fn(order: pd.Series) : 
        return (((today == order_date) or (order.iloc[0].ot == "SH")) and all([
              order.on.count() <= max_lines ,
              (order.on.iloc[0] not in prev_order_total_values) or abs((order.t * order.cq).sum() - prev_order_total_values[order.on.iloc[0]]) <= 1 , 
              "WHOLE" not in order.m.iloc[0] ,+
              (order.t * order.cq).sum() >= 200
            ])) or (order.on.iloc[0] in forced_order_nos)

    ##Intiate the Ikea Billing Session
    order_objects:list[models.Orders] = []
    try :  
        billing = Billing(order_date = order_date,filter_orders_fn = filter_orders_fn)
    except Exception as e: 
        print("Billing Session Failed\n" , traceback.format_exc() )
        billing_log.error = str(traceback.format_exc())
        billing_log.status = BillingStatus.Failed
        billing_log.save()
        billing_lock.release()
        return
    
    ##Functions combing Ikea Session + Database 
    def PrevDeliveryProcess() : 
        billing.Prevbills()
        models.Sales.objects.filter(inum__in = billing.prevbills).update(delivered = False)

    def CollectionProcess() : 
        billing.Collection()
        models.PushedCollection.objects.bulk_create([ models.PushedCollection(
                   billing = billing_log, party_code = pc) for pc in billing.pushed_collection_party_ids ])
        
    def OrderProcess() : 
        billing.Order(delete_order_nos)
        last_billing_orders = billing.all_orders       
        if len(last_billing_orders.index) == 0 : return 

        models.Party.objects.bulk_create([ 
            models.Party( name = row.p ,code = row.pc ) 
            for _,row in last_billing_orders.drop_duplicates(subset="pc").iterrows() ],
         update_conflicts=True,
         unique_fields=['code'],
         update_fields=["name"])
        filtered_orders = billing.filtered_orders.on.values
        
        ## Warning add and condition 
        order_objects.extend( models.Orders.objects.bulk_create([ 
            models.Orders( order_no=row.on,party_id = row.pc,salesman=row.s, 
                    creditlock = ("Credit Exceeded" in row.ar) , place_order = (row.on in filtered_orders) , 
                beat_id = row.mi , billing = billing_log , date = datetime.datetime.now().date() , type = row.ot   ) 
            for _,row in last_billing_orders.drop_duplicates(subset="on").iterrows() ],
         update_conflicts=True,
         unique_fields=['order_no'],
         update_fields=["billing_id","type","creditlock","place_order"]) )
        
        prev_allocated_value = { order.order_no :  order.allocated_value() for order in order_objects }

        models.OrderProducts.objects.filter(order__in = order_objects,allocated = 0).update(allocated = F("quantity"),reason = "Guessed allocation")
        models.OrderProducts.objects.bulk_create([ models.OrderProducts(
            order_id=row.on,product=row.bd,batch=row.bc,quantity=row.cq,allocated = row.aq,rate = row.t,reason = row.ar) for _,row in last_billing_orders.iterrows() ] , 
         update_conflicts=True,
         unique_fields=['order_id','product','batch'],
         update_fields=['quantity','rate','allocated','reason'])

        curr_allocated_value = { order.order_no :  order.allocated_value() for order in order_objects }
        for order in order_objects : 
            diff = curr_allocated_value[order.order_no] - prev_allocated_value[order.order_no]
            if diff >= 1 : 
                order.release = False
                order.force_order = False
                order.save()
        
    def ReportProcess() :
        sync_reports(billing,limits={"sales" : None , "adjustment" : None , "collection" : None })
        models.Sales.objects.filter(inum__in = billing.prevbills).update(delivered = False)
        for order in order_objects :                     
            outstanding_qs = models.Outstanding.objects.filter(party = order.party,beat = order.beat.name,balance__lte = -1)
            today_bill_count = models.Sales.objects.filter(party = order.party,beat = order.beat.name,
                                                           date = datetime.date.today()).count()
            if (today_bill_count == 0) and (outstanding_qs.count() == 1) : 
                bill_value = order.bill_value()
                outstanding_bill:models.Outstanding = outstanding_qs.first() # type: ignore
                outstanding_value = -outstanding_bill.balance 

                if bill_value < 200 : continue
                
                max_outstanding_day =  (today - outstanding_bill.date).days
                max_collection_day = models.Collection.objects.filter(party = order.party , date = today).aggregate(date = Max("bill__date"))["date"]
                max_collection_day = (today - max_collection_day).days if max_collection_day else 0   
                if (max_collection_day > 21) or (max_outstanding_day > 21): 
                    continue 
                if (bill_value <= 500) or (outstanding_value <= 500):
                    order.release = True 
                    order.save()
                    
    def DeliveryProcess() : 
        billing.Delivery()
        if len(billing.bills) == 0 : return 
        billing_log.start_bill_no = billing.bills[0]
        billing_log.end_bill_no = billing.bills[-1]
        billing_log.bill_count = len(billing.bills)
        billing_log.save()

    ##Start the proccess
    billing_process_functions = [ billing.Sync , PrevDeliveryProcess ,  (lambda : billing.release_creditlocks(creditrelease)) , 
                                  CollectionProcess ,  OrderProcess ,  DeliveryProcess , ReportProcess  ]   
    billing_process =  dict(zip(billing_process_names,billing_process_functions)) 
    billing_failed = False 
    for process_name,process in billing_process.items() : 
        process_obj = models.BillingProcessStatus.objects.get(billing=billing_log,process=process_name)
        process_obj.status = BillingStatus.Started
        process_obj.save()    
        start_time = time.time()
        
        try : 
            process()              
        except Exception as e :
            traceback.print_exc()
            billing_log.error = str(traceback.format_exc())
            billing_failed = True 

        process_obj.status = (BillingStatus.Failed if billing_failed else  BillingStatus.Success)
        end_time = time.time()
        process_obj.time = round(end_time - start_time,2)
        process_obj.save()

        if billing_failed :  break 
        
    billing_log.end_time = datetime.datetime.now() 
    billing_log.status = BillingStatus.Failed if billing_failed else  BillingStatus.Success
    billing_log.save()
    billing_lock.release()

def get_last_billing() :
    billing_qs =  models.Billing.objects.filter(start_time__gte = datetime.date.today()).order_by("-start_time") 
    last_billing = billing_qs.first()      
    if last_billing : 
        order_status = models.BillingProcessStatus.objects.filter(billing = last_billing,process = "ORDER").first()
        if order_status and (order_status.status in [BillingStatus.Success,BillingStatus.Failed]) :  pass
        else : 
            if billing_qs.count() > 1 : 
                last_billing = billing_qs[1]
    return last_billing

Permission = Enum("Permission","add delete change")

class ModelPermission() : 
    permissions = []
    
    def has_add_permission(self, request,obj = None):
        return (Permission.add in self.permissions) 

    def has_change_permission(self, request, obj=None):
        return Permission.change in self.permissions 
    
    def has_delete_permission(self, request, obj=None):
        return Permission.delete in self.permissions

class CustomAdminModel(ModelPermission,admin.ModelAdmin) : 
    
    show_on_navbar = True
    permissions = []
    custom_views:list[tuple[str,str|Callable]] = []
    hidden_fields = []

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.custom_admin_urls = []

    def save_changelist(self,request) :
        """Safe Work Around to Only save changelist forms (even works with actions, it doesnt trigger actions)""" 
        original_post = request.POST.copy()
        edited_post = request.POST.copy()
        edited_post["_save"] = "Save"
        request._set_post(edited_post)
        super().changelist_view( request )
        request._set_post(original_post)

    def get_urls(self) :
        urls =  super().get_urls()
        custom_urls = [ path(f'{view_name.rstrip("/")}/', 
                             self.admin_site.admin_view( getattr(self,view_fn) if isinstance(view_fn,str) else view_fn ), name=view_name.split("/")[0]) 
                             for view_name , view_fn in self.custom_views ] ## Supports viewname/<str:param>
        return custom_urls + urls 
    
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj:  
            return [field for field in fields if field not in self.hidden_fields]
        return fields


class BaseOrderAdmin(CustomAdminModel) :   
    
    class OrderProductsInline(ModelPermission,admin.TabularInline) : 
        model = models.OrderProducts
        show_change_link = True
        verbose_name_plural = "products"

    inlines = [OrderProductsInline]
    readonly_fields = ("order_no",'date','party','type','salesman','beat','billing','release','creditlock','delete','place_order','force_order')

    @bold 
    def pending_value(self,obj) : 
        return round(obj.bill_value() - obj.allocated_value(),2)
    
    @bold 
    def allocated_value(self,obj) : 
        return round(obj.allocated_value(),2)
    
    @bold 
    def value(self,obj) : 
        return obj.bill_value()
    

    def OS(self,obj) :
        today = datetime.date.today() 
        bills = [  f"{-round(bill.balance)}*{(today - bill.date).days}"
                 for bill in models.Outstanding.objects.filter(party = obj.party,beat = obj.beat.name,balance__lte = -1).all() ]
        return "/ ".join(bills)
    
    def coll(self,obj) : 
        today = datetime.date.today() 
        coll = [  f"{round(coll.amt or 0)}*{(today - coll.bill.date).days}"
                 for coll in models.Collection.objects.filter(party = obj.party , date = today).all() ]
        return "/ ".join(coll)
    
    def phone(self,obj) : 
        phone = obj.party.phone or "-"
        return hyperlink(url = "tel:+91" + phone, text = phone)

    @bold
    def lines(self,obj) : 
        return len([ product for product in obj.products.all() if product.allocated != product.quantity])
    
    @admin.display(boolean=True)
    def partial(self,obj) :
        return obj.partial()

    def cheque(self,obj) : 
        qs = models.SalesmanCollection.objects.filter(time__gte = datetime.date.today()).filter(bills__inum__party = obj.party)
        colls = qs.all()
        if len(colls) : 
            ids = ",".join([ str(coll.id) for coll in colls ])
            day_values = defaultdict(lambda : 0) 
            today = datetime.date.today()
            for coll in colls : day_values[(coll.date - today).days] += coll.amt  
            return hyperlink(f'/app/salesmancollection/?id__in={ids}',"/".join([ f"{round(amt)}*{day}" for day,amt in day_values.items() ])) 
        else : 
            return ""

    @admin.action(description="Force Place Order & Release Lock")
    def force_order(self, request, queryset) : 
        queryset.update(place_order = True,force_order=True)
        queryset.filter(creditlock=True).update(release = True)
    
    @admin.action(description="Delete Orders")
    def delete_orders(self, request, queryset) : 
        queryset.update(delete = True)

class BaseProcessStatusAdmin(CustomAdminModel) : 
    process_names = []
    process_logs = []
    
    actions = None
    ordering = ("id",)
    class Media:
            css = { 'all': ('admin/css/process_status.css',) }

    @admin.display(description="")
    def colored_status(self,obj):
        class_name = ["unactive","green","blink","red"][obj.status]
        return format_html(f'<span class="{class_name} indicator"></span>')
    
    def time(self):
        return (f"{self.time} SEC") if self.time is not None else '-'

    def process(self) : 
        return self.process.upper().replace("_"," ") # type: ignore
    
    list_display = ["colored_status",process,time]

    def create_logs(self) :
        self.model.objects.all().delete()
        self.process_logs = []
        for process_name in self.process_names : 
            process = self.model(process = process_name , status = ProcessStatus.NotStarted)
            self.process_logs.append(process)
            process.save()  

    def run_processes(self,processes) : 
        for process_name,process_log,process in zip(self.process_names,self.process_logs,processes,strict=False) : 
            process_log.status = ProcessStatus.Started
            process_log.save()
            start_time = time.time()
            process_failed = False 
            try :
                process()
                process_failed = False
            except Exception as e :
                process_failed = True
                print(f"Error in {self.model} - {process_name} process : {e}")

            process_log.status = (ProcessStatus.Failed if process_failed else  ProcessStatus.Success)
            end_time = time.time()
            process_log.time = round(end_time - start_time,2)
            process_log.save()

#Dummy Admins 
class PartyAdmin(CustomAdminModel) : 
    search_fields = ["name"]
    ordering = ["name"] 
    class OutstandingInline(admin.TabularInline) : 
        model = models.Outstanding
        def get_queryset(self,request) : 
            return super().get_queryset(request).filter(balance__lte = -1)

    inlines = [OutstandingInline]
    def get_queryset(self,request) :
        parties = models.Sales.objects.filter(date__gte = datetime.date.today() - datetime.timedelta(weeks=16)).values_list("party_id",flat=True)
        return super().get_queryset(request).filter(code__in = parties)



## Billing Admin
class BillingAdmin(BaseOrderAdmin) :   

    change_list_template = "billing.html"
    list_display_links = ["party"]
    list_display = ["release","party","lines","value","OS","coll","salesman","beat","phone","delete","type","cheque"] 
    list_editable = ["release","delete"]
    ordering = ["-release","salesman"]
    actions = None
    permissions = [Permission.change]

    def get_bill_statistics(self,request:HttpRequest) -> list[ChangeList]: 

        class BillingProcessStatusAdmin(BaseProcessStatusAdmin) :
             sortable_by = []
             def get_queryset(self, request):
                 qs = super().get_queryset(request)
                 last_process = qs.last()
                 return qs.filter(billing = last_process.billing) if last_process else qs 
                        
        ## Billing Statistics Admin (Abstract class)
        class BillStatisticsAdmin(admin.ModelAdmin): 
            actions = None
            list_display = ["type","count"]
            sortable_by = []
            ordering = ("id",)

        class LastBillStatisticsAdmin(BillStatisticsAdmin):
            def get_queryset(self, request: HttpRequest) -> QuerySet[models.BillStatistics]:
                return super().get_queryset(request).filter(type__contains="LAST")

        class TodayBillStatisticsAdmin(BillStatisticsAdmin):
            def get_queryset(self, request: HttpRequest) -> QuerySet[models.BillStatistics]:
                return super().get_queryset(request).exclude(type__contains="LAST")

        today = datetime.date.today()

        today_stats = models.Sales.objects.filter(date  = today,type = "sales").exclude(beat__contains = "WHOLE").aggregate(
            bill_count = Count("inum") ,  start_bill_no = Min("inum") , end_bill_no = Max("inum") 
        )

        today_stats |= models.Billing.objects.filter(start_time__gte = today).aggregate( 
            success = Count("status",filter=Q(status = BillingStatus.Success)) , failures = Count("status",filter=Q(status = BillingStatus.Failed))
        )

        last_billing = models.Billing.objects.filter(start_time__gte = today).order_by("-start_time").first() or models.Billing(status = BillingStatus.NotStarted,id=-1)

        orders_qs = models.Orders.objects.filter(billing = last_billing).exclude(beat__name__contains = "WHOLE") 
        orders_qs = orders_qs.exclude(products__allocated = F("products__quantity")).distinct()

        stats =   { "TODAY BILLS COUNT" : today_stats["bill_count"] , 
                    "TODAY BILLS" : f'{today_stats["start_bill_no"]} - {today_stats["end_bill_no"]}' ,
                    "SUCCESS" : today_stats["success"] , "FAILURES" : today_stats["failures"] ,
                    "LAST BILLS COUNT" : last_billing.bill_count or "-" , #"LAST COLLECTION COUNT" : last_billing.collection.count() if last_billing.pk else "-" ,   
                    "LAST BILLS" : f'{last_billing.start_bill_no or ""} - {last_billing.end_bill_no or ""}', 
                    "LAST STATUS" :  BillingStatus(last_billing.status).name.upper() , 
                    "LAST TIME" : f'{last_billing.start_time.strftime("%H:%M:%S") if last_billing.start_time else "-"}' ,
                    "LAST REJECTED": orders_qs.filter(place_order = False).count()  , 
                    "LAST PENDING" : orders_qs.filter(place_order = True,creditlock=False).count() }


        models.BillStatistics.objects.all().delete()
        models.BillStatistics.objects.bulk_create([ models.BillStatistics(type = type,count = str(value)) for type,value in stats.items() ])

        admin_models = ((LastBillStatisticsAdmin,models.BillStatistics),(BillingProcessStatusAdmin,models.BillingProcessStatus),(TodayBillStatisticsAdmin,models.BillStatistics))
        tables = [ admin(model,admin_site).get_changelist_instance(request) for admin,model in admin_models ]
        for table in tables : table.formset = None 

        return tables 

    def start(self,billing_form:forms.Form) :
        if not billing_lock.acquire(blocking=False) : 
            return False
        ## Neccesary to create the billing_log before sending response , as the creditlock table depends on the latest billing
        billing_log = models.Billing(start_time = datetime.datetime.now(), status = 2,date = billing_form.cleaned_data.get("date",datetime.date.today()) )
        billing_log.save()
        for process_name in billing_process_names :
            models.BillingProcessStatus(billing = billing_log,process = process_name,status = 0).save()    
        thread = threading.Thread( target = run_billing_process , args = (billing_log,billing_form,) )
        thread.start() 
        return True 

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(creditlock=True) 
        #2 hrs of yesterday 
        billing_qs = models.Billing.objects.filter(start_time__gte = datetime.datetime.now()  - datetime.timedelta(minutes=120)).order_by("-start_time")
        for billing in billing_qs:
            order_status = models.BillingProcessStatus.objects.filter(billing=billing, process="ORDER").first()
            if order_status and order_status.status in [BillingStatus.Failed, BillingStatus.Success]:
                return qs.filter(billing=billing, place_order=True)
        return qs.none()
    
    def changelist_view(self, request, extra_context=None): 
         ## This attribute says get_queryset function whether to filter the creditlocks only for last billing (or) all billing
        INF_TIME = 1e7
        Actions = Enum("Actions",(("Start","start"),("Refresh","refresh"),("Quit","quit")))

        class BillingForm(forms.Form) : 
            max_lines = forms.IntegerField(initial=100,  widget=forms.TextInput(attrs={'placeholder': 'Maximum Lines'}))
            time_interval = forms.IntegerField(initial=10, widget=forms.TextInput(attrs={'placeholder': 'Time Interval'}))
            action = forms.TypedChoiceField(choices=list((action.value, action.name) for action in Actions), initial=Actions.Quit.name,coerce=Actions)
            date = forms.DateField(required=False,initial=datetime.date.today(), widget=forms.DateInput(attrs={'placeholder': 'Bill Date','type' : 'date'}))
            einvoice = forms.BooleanField(required=False,initial=True,label="E-Invoice")

        
        next_action_time_interval = INF_TIME
        next_action = Actions.Quit 

        if request.method == "POST" : 
            form = BillingForm(request.POST)
            if form.is_valid() : 
                curr_action = form.cleaned_data["action"]
                if (curr_action == Actions.Start) or (curr_action == Actions.Quit) : self.save_changelist(request)

                if curr_action == Actions.Quit :
                    if billing_lock.locked() :
                        reload_server() 
                        billing_lock.release()

                if curr_action == Actions.Start : 
                    self.start(billing_form = form)
                    next_action = Actions.Refresh 

                if curr_action == Actions.Refresh : 
                    next_action = Actions.Refresh if billing_lock.locked() else Actions.Start
                
                action_time_map = { Actions.Start : form.cleaned_data["time_interval"] * 60 , Actions.Refresh : 5 , Actions.Quit : INF_TIME }
                next_action_time_interval = action_time_map[ next_action ] * 1000 
        else : 
            form = BillingForm()

        tables = self.get_bill_statistics(request) 
        return super().changelist_view( request , extra_context={ "title" : "" ,"tables" : tables ,  "form" : form ,  
        "next_action_time_interval" : next_action_time_interval , "next_action" : next_action.value  })  # type: ignore

class OrdersAdmin(BaseOrderAdmin) :
    
    list_display_links = ["order_no"]
    list_display =  ["partial","order_no","party","lines","allocated_value","OS","coll","salesman","beat","creditlock","delete","phone"] 
    ordering = ["place_order"]
    actions = ["force_order","delete_orders"]
    custom_views = [ ("pending_orders","pending_changelist_view"),
                     ("rejected_orders","rejected_changelist_view") ]

    custom_filter_functions = {
     'less_than_200':  lambda qs :  qs.annotate(bill_value_field = Sum(F('products__quantity') * F('products__rate'))).filter(
                                                bill_value_field__lt = 200).order_by("bill_value_field") , 
     'less_than_10_lines' :  lambda qs : qs.annotate(lines_count = Count(F('products'))).filter(lines_count__lt = 10) ,
     'already_billed' :  lambda qs : qs.filter(order_no__in = [ order.order_no for order in qs if order.partial() ]) 
     } 

    last_filter_functions = { 'last' : lambda qs : qs.filter(billing = get_last_billing()) } 

    list_filter = [create_simple_admin_list_filter("Filter","filter",custom_filter_functions), 
                   create_simple_admin_list_filter("Billing","billing",last_filter_functions)]

    def get_queryset(self, request):
        qs = super().get_queryset(request)     
        view_name = request.resolver_match.view_name 
        
        if view_name.endswith("pending_orders") : 
            qs = qs.filter(place_order = True,creditlock=False) 
            qs = qs.exclude(products__allocated = F("products__quantity")).distinct()

        if view_name.endswith("rejected_orders") : qs = qs.filter(place_order = False)

        qs = qs.exclude(beat__name__contains = "WHOLE")
        return qs 
    
    def _changelist_view(self,title_prefix,request,extra_context) : 
        last_billing = get_last_billing()
        title = f"{title_prefix} @ {last_billing.start_time.strftime('%d %B %Y, %I:%M:%S %p')}" if last_billing else "No Recent Billing"
        return super().changelist_view(request, extra_context={ "title" : title })
    
    def changelist_view(self,request,extra_context = {}) : 
        return self._changelist_view("All Orders",request,extra_context)
    
    def pending_changelist_view(self,request,extra_context = {}) : 
        return self._changelist_view("Pending Orders",request,extra_context)
    
    def rejected_changelist_view(self,request,extra_context = {}) : 
        return self._changelist_view("Rejected Orders",request,extra_context)

class OutstandingAdmin(CustomAdminModel) : 

    change_list_template = "form_and_changelist.html"
    list_display = ["inum","party","beat","balance","phone","days"]
    ordering = ["date"]
    search_fields = ["party__name","beat"]
    days_filter = { f'>= {no_of_days} days': functools.partial(lambda no_of_days,qs: qs.filter(date__lte=datetime.date.today() - datetime.timedelta(days=no_of_days)) 
                                                               ,no_of_days) for no_of_days in [14,21,28,30] }
    
    list_filter = [ create_simple_admin_list_filter("Outstanding Days","days",days_filter) ]
    custom_views = [("get-outstanding-report","get_outstanding_report")]

    class OutstandingForm(forms.Form) : 
            date = forms.DateField(required=False,initial=datetime.date.today(),widget=forms.DateInput(attrs={'type' : 'date'}))
            type = forms.ChoiceField(required=False,choices=(("Retail","Retail"),("Wholesale","Wholesale")),initial=True)
            Submit = submit_button("Download")
            Action = reverse_lazy("admin:get-outstanding-report")
            
    def phone(self,obj) : 
        return obj.party.phone
    
    def days(self,obj) : 
        return (datetime.date.today() - obj.date).days
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).filter(balance__lte = -1)
    
    def get_outstanding_report(self,request) : 
        form = self.OutstandingForm(request.POST)
        if not form.is_valid() : return 
        date = form.cleaned_data.get("date")or self.today
        day = date.strftime("%A").lower()
        
        outstanding:pd.DataFrame = query_db(f"""
        select salesman_name as salesman , (select name from app_party where party_id = code) as party , beat , inum as bill , 
        (select -amt from app_sales where inum = app_outstanding.inum) as bill_amt , -balance as balance , 
        (select phone from app_party where code = party_id) as phone , 
        round(julianday('{date}') - julianday(date)) as days , 
        days as weekday 
        from app_outstanding left outer join app_beat on app_outstanding.beat = app_beat.name
        where  balance <= -1 
        """,is_select = True)  # type: ignore 

        IGNORED_PARTIES_FOR_OUTSTANDING = ["SUBASH ENTERPRISES","TIRUMALA AGENCY-P","TIRUMALA AGENCY-D","ANANDHA GENERAL MERCHANT-D-D-D"]
        outstanding = outstanding[~outstanding["party"].isin(IGNORED_PARTIES_FOR_OUTSTANDING)]
        if form.cleaned_data["type"] == "Wholesale" : outstanding = outstanding[outstanding["beat"].str.contains("WHOLESALE")] 
        if form.cleaned_data["type"] == "Retail" : outstanding = outstanding[~outstanding["beat"].str.contains("WHOLESALE")] 
        outstanding["coll_amt"] = outstanding["bill_amt"] - outstanding["balance"]
        outstanding = outstanding[["salesman","beat","party","bill","bill_amt","coll_amt","balance","days","phone","weekday"]]
        pivot_fn = lambda df : pd.pivot_table(df,index=["salesman","beat","party","bill"],values=['bill_amt','coll_amt','balance',"days","phone"],aggfunc = "first")[['bill_amt','coll_amt','balance',"days","phone"]] # type: ignore
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        pivot_fn(outstanding[ (outstanding.days >= 21) & outstanding.weekday.str.contains(day) ]).to_excel(writer, sheet_name='21 Days')
        pivot_fn(outstanding[outstanding.days >= 28]).to_excel(writer, sheet_name='28 Days')
        outstanding.sort_values("days",ascending=False).to_excel(writer, sheet_name='ALL BILLS',index=False)
        writer.close()
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="' + f"outstanding_{date}.xlsx" + '"'
        return response 

    def changelist_view(self, request, extra_context=None):    
        TIME_LIMIT = 10*60 
        sync_reports(limits={"sales":TIME_LIMIT,"collection":TIME_LIMIT,"adjustment":TIME_LIMIT})
        return super().changelist_view(request, (extra_context or {})| {"title" : "Outstanding Report", "form" : self.OutstandingForm() })
    
class SalesCollectionAdmin(CustomAdminModel) :

    class SalesCollectionBillInline(ModelPermission,admin.TabularInline) : 
        model = models.SalesmanCollectionBill
        verbose_name_plural = "bills"
        list_display = ["inum","amt"]
    
    list_display = ["party","cheque_date","amt","salesman","time"]
    date_filter_fn = { key: functools.partial(lambda days,qs: qs.filter(time__date = (datetime.date.today() - datetime.timedelta(days=days))) , no_of_days) 
                                for key,no_of_days in [("Today",0),("Yesterday",1),("Day Before Yesterday",2)] }
    list_filter = [create_simple_admin_list_filter("Collection Entry Time","time",date_filter_fn),"salesman"]
    ordering = ["salesman"]    
    inlines = [SalesCollectionBillInline]
    
    
    def cheque_date(self,obj) : 
        return obj.date 
    
    def has_delete_permission(self, request, obj=None):
        return True
    
    def delete_queryset(self,request,queryset) : 
        for obj in list(queryset) : 
            obj.delete()

    def changelist_view(self, request: HttpRequest, extra_context = {}) -> TemplateResponse:
        return super().changelist_view(request, extra_context = extra_context | {"title" : ""}) # type: ignore
        

def create_admin_form_filter(title,form) : 
    class CustomFormFilter(NumericRangeFilter):
        template = "rangefilter/custom_filter.html"
        def _get_default_title(self, request, model_admin, field_path):
            return title
        def _get_form_class(self):
            return form
        def expected_parameters(self):
            return form().fields.keys()
    return CustomFormFilter

class PrintAdmin(CustomAdminModel) :

    class PartyAutocomplete(autocomplete.Select2ListView):
        def get_list(self): 
            qs = models.Sales.objects.filter(date__gte = datetime.date.today() - datetime.timedelta(weeks=16))
            beat = self.forwarded.get('beat', None)
            if beat : qs = qs.filter(beat = beat)
            parties = qs.annotate(
                keyword = Concat('party__name', Value(' ('), 'party__master_code', Value(')') , output_field=CharField())
            ).values_list("keyword",flat=True).distinct() #warning
            return parties 

    @admin.display(boolean=True)
    def delivered(obj): 
        return obj.bill.delivered
    
    def s(self,obj) :
        if obj.loading_sheet is None : return "-"
        return obj.loading_sheet.party 
    
    def t(self,obj): 
        return obj.delivered_time  
    
    permissions = [Permission.change]
    change_list_template = "form_and_changelist.html"
    list_display = ["bill","party","salesman","print_type","print_time","einvoice","amount",delivered,"vehicle"]#,"einvoice","ctin"]
    ordering = ["bill"]
    actions = ["both_copy","loading_sheet_salesman","loading_sheet","first_copy","double_first_copy","second_copy","printed_by_mistake",
               "add_to_loading_sheet","remove_from_loading_sheet"]
    custom_views = [("print_party_autocomplete",PartyAutocomplete.as_view()),
                    ("undo_print","undo_print")]
    list_per_page = 250
    readonly_fields = ["bill"] #,"print_type","print_time" 
    title = "All Bills"

    PRINT_ACTION_CONFIG = {
        PrintType.FIRST_COPY: {
            'create_bill': lambda billing, group, context,cash_bills : 
                     billing.Download(bills=group,pdf=True, txt=False,cash_bills=cash_bills) or 
                     pdf_create.remove_blank_pages_from_first_copy("bill.pdf") or 
                    aztec.add_aztec_codes_to_pdf("bill.pdf","bill.pdf",PrintType.FIRST_COPY) ,
            'file_names': "bill.pdf",
            'update_fields': lambda context : {'print_type': PrintType.FIRST_COPY.value} ,
            'allow_printed'  : False , 
        },
        PrintType.SECOND_COPY: {
            'create_bill': lambda billing, group, context,cash_bills : billing.Download(bills=group,pdf=False, txt=True,cash_bills=cash_bills) or 
                                                            secondarybills.main('bill.txt', 'bill.docx',aztec.generate_aztec_code),
            'file_names': "bill.docx" ,
            'allow_printed'  : True , 
        },
        PrintType.LOADING_SHEET: {
            'create_bill': lambda billing, group, context,cash_bills: pdf_create.loading_sheet_pdf(billing.loading_sheet(group), 
                                                                                    sheet_type=pdf_create.LoadingSheetType.Plain) 
                                                            or models.Bill.objects.filter(bill_id__in = group).update(plain_loading_sheet=True) ,
            'file_names': "loading.pdf", 
            'allow_printed'  : True , 
        },
        PrintType.LOADING_SHEET_SALESMAN: {
            'create_bill': lambda billing, group, context,cash_bills : 
                    pdf_create.loading_sheet_pdf(billing.loading_sheet(group), sheet_type=pdf_create.LoadingSheetType.Salesman,
                                                context=context) or 
                    aztec.add_aztec_codes_to_pdf("loading.pdf","loading.pdf",PrintType.LOADING_SHEET_SALESMAN) ,
            'file_names': "loading.pdf,loading.pdf",
            'get_context': lambda request,queryset: {
                'salesman': models.Beat.objects.filter(name = queryset.first().bill.beat).first().salesman_name if queryset.exists() else '' , 
                'beat': queryset.first().bill.beat if queryset.exists() else '' , 
                'party' : request.POST.get("party_name") , 
                'inum' : "SM" + queryset.first().bill.inum  ,
            },
            'update_fields': lambda context : {'print_type': PrintType.LOADING_SHEET.value , 
                                               'loading_sheet' : models.SalesmanLoadingSheet.objects.create(**context) } , 
            'allow_printed'  : False , 
        }
    }
    PRINT_ACTION_CONFIG[PrintType.DOUBLE_FIRST_COPY] = PRINT_ACTION_CONFIG[PrintType.FIRST_COPY] | {"file_names":"bill.pdf,bill.pdf"}

    # Function to filter the bills for a given salesman 
    @staticmethod
    def get_salesman_bills(salesman,queryset):
            beats = list(models.Beat.objects.filter(salesman_name = salesman).values_list("name",flat=True).distinct())
            return queryset.filter(bill__beat__in = beats)
    
    def get_list_filter(self, request): # type: ignore
        
        class BillRangeForm(forms.Form) : 
                bill_id__gte = forms.CharField(
                    required=False, 
                    label = "",
                    widget=forms.TextInput(attrs={"placeholder" : "From Bill"})
                )
                bill_id__lte = forms.CharField(
                    required=False, 
                    label = "",
                    widget=forms.TextInput(attrs={"placeholder" : "To Bill"})
                )
                class Media:
                    css = {
                        'all': ('css/rangefilter.css',)  
                    }

        date_filter_fn = { key: functools.partial(lambda days,qs: qs.filter(bill__date = (datetime.date.today() - datetime.timedelta(days=days))) , no_of_days) 
                        for key,no_of_days in [("Today",0),("Yesterday",1),("Day Before Yesterday",2)] }
        return [
            create_simple_admin_list_filter("Printed ?", "printed", {
                'Not Printed': lambda qs: qs.filter(print_time__isnull=True) , 
                "Plain Loading Sheet" : lambda qs : qs.filter( Q(plain_loading_sheet=True) | Q(print_time__isnull=True) )
            }),
            # ("bill_id",create_admin_form_filter("Bill",BillRangeForm)),
            create_simple_admin_list_filter("Bill Date","bill__date",date_filter_fn),
            create_simple_admin_list_filter("Salesman", "salesman", {
                salesman: functools.partial(self.get_salesman_bills, salesman)
                for salesman in models.Beat.objects.all().values_list("salesman_name", flat=True).distinct()
            }),
            create_simple_admin_list_filter("Delivered","bill__delivered",
                                            {"Yes" : lambda qs : qs.filter(bill__delivered = True) ,
                                             "No" : lambda qs : qs.filter(bill__delivered = False) }),
        ]
     
    def date(self,obj):
        return obj.bill.date
    
    def ctin(self,obj):
        return obj.bill.ctin
    
    def amount(self,obj):
        return round(abs(obj.bill.amt))
    
    @admin.display(boolean=True)
    def einvoice(self,obj):  
        return bool(obj.bill.ctin is None) or bool(obj.irn)
    
    def salesman(self,obj) :
        beat = models.Beat.objects.filter(name = obj.bill.beat).first()
        return beat.salesman_name if beat else None

    def party(self,obj) : 
        return obj.bill.party.name
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request) #.filter(bill__date__gte = datetime.date.today() - datetime.timedelta(days=2)) #change

    def changelist_view(self, request: HttpRequest, extra_context = {}) -> TemplateResponse:
        sync_reports(limits={"sales":5*60})
        bill_count = self.get_queryset(request).filter(print_time__isnull = True,bill__date = datetime.date.today()).count()
        warning = "(Einvoice Disabled)" if not models.Settings.objects.get(key = "einvoice").status else ""
        return super().changelist_view(request, extra_context | {"title" : f"{self.title} - {bill_count} Not Printed Today {warning}"})

    def handle_einvoice_upload(self,request,einv_qs):
        # Aggregate date range for the invoices
        billing = Billing()
        dates = einv_qs.aggregate(fromd=Min("bill__date"), tod=Max("bill__date"))
        from_date, to_date = dates["fromd"], dates["tod"]

        # Generate e-invoice JSON from Billing
        inums = einv_qs.values_list("bill_id", flat=True)
        bytesio = billing.einvoice_json(fromd=from_date, tod=to_date, bills=inums)
        if bytesio : 
            json_str = bytesio.getvalue().decode('utf-8')  # Convert BytesIO to string
            print(json_str)
            success, failures = Einvoice().upload(json_str)
            failed_inums = failures.get("Invoice No", []).tolist()
            if failures.shape[0]:
                print(failures)
                messages.error(request, f"E-Invoice upload failed for {failed_inums}\nThese bills will not be printed.")
        else :
            failed_inums = inums
            messages.error(request, "No data generated for e-invoice upload.")

        # Process today's e-invoices
        today_einvs_bytesio = BytesIO(Einvoice().get_today_einvs())
        try :
            response = billing.upload_irn(today_einvs_bytesio)
        except JSONDecodeError as e : 
            messages.error(request,"Error uploading irn to ikea")
            return 

        # Handle IRN upload failures
        if not response["valid"]:
            raise Exception(f"IRN Upload Failed: {response}")

        # Process the successful e-invoices
        einvoice_df = pd.read_excel(today_einvs_bytesio)
        for _,row in einvoice_df.iterrows() : 
            models.Bill.objects.filter(bill_id = row["Doc No"].strip()).update(irn = row["IRN"].strip())
                
        # Remove successfully processed invoices from the failed list
        processed_bills = einvoice_df["Doc No"].values
        failed_inums = list(set(failed_inums) - set(processed_bills))

        return failed_inums

    def print_bills(self, request, billing: Billing, queryset, print_type: PrintType,merger):

        config = self.PRINT_ACTION_CONFIG[print_type]
        bills = [bill.bill_id for bill in queryset]
        cash_bills = [bill.bill_id for bill in queryset.filter(cash_bill = True)]

        # Get additional context for the action (like salesman details if needed)
        context = {}
        if config.get('get_context') :
            context = config['get_context'](request,queryset)
        
        config['create_bill'](billing, bills, context, cash_bills)
        file_names = config['file_names'].split(",")
        for file in file_names :
            if file.endswith(".docx") : 
                os.system(f"libreoffice --headless --convert-to pdf {file}")
                file = file.replace(".docx",".pdf") 
            with open(file, "rb") as pdf_file:
                merger.append(pdf_file)
        
        if 'update_fields' in config:
            queryset.update(**config['update_fields'](context), print_time=datetime.datetime.now())
                
    def base_print_action(self, request, queryset, print_types):
        queryset = queryset.filter(bill__delivered = True)
        
        einv_qs =  queryset.filter(bill__ctin__isnull=False, irn__isnull=True) #warning #.none to prevent einvoice
        einvoice_enabled = models.Settings.objects.get(key = "einvoice").status 
        einv_count = einv_qs.count() if einvoice_enabled else 0
        einvoice_service = Einvoice() if einvoice_enabled  else None 

        if ('confirm_action' in request.POST) and ("captcha" in request.POST):
            captcha = request.POST["captcha"].upper()
            is_success , error = einvoice_service.login(captcha)
            if error : messages.error(request,f"Einvoice Login Failed : {error}")

        if (einv_count==0) or einvoice_service.is_logged_in():
            if einv_count:
                self.handle_einvoice_upload(request,einv_qs)

            billing = Billing()
            bills = list(queryset.values_list('bill_id', flat=True))
            if len(bills) == 0 : return 
            merger = PdfMerger()
            for print_type in print_types:
                allow_already_printed = self.PRINT_ACTION_CONFIG[print_type]["allow_printed"]
                queryset = models.Bill.objects.filter(bill_id__in=bills)
                if not allow_already_printed: 
                    already_printed = queryset.filter(print_time__isnull=False) 
                    if already_printed and already_printed.exists():
                        messages.warning(request, f"Bills are already printed for {already_printed.values_list('bill_id', flat=True)}")
                    queryset = queryset.filter(print_time__isnull=True)
                    self.print_bills(request, billing, queryset, print_type, merger)
                else : 
                    self.print_bills(request, billing, queryset, print_type, merger)
            merger.write("bill.pdf")
            merger.close()
            code = f"""
            <script>
            const url = '/static/bill.pdf' ; // Replace with the desired URL
            const iframe = document.createElement("iframe");
            iframe.style.display = "none";
            iframe.src = url;
            document.body.appendChild(iframe);

            iframe.onload = () => {{
                iframe.contentWindow.focus(); // Focus on iframe content
                iframe.contentWindow.print(); // Trigger the print command
            }};
            </script>
            """
            undo_url = reverse("admin:undo_print") + f"?inums={','.join(bills)}" + f"&next={quote(str(request.get_full_path()))}"
            undo_link = hyperlink(undo_url,"Printed By Mistake?",style="text-decoration:underline;color:blue;margin-left:5px;",new_tab=False) 
            link = hyperlink(f"/static/bill.pdf",f"{bills[0]} - {bills[-1]}",style="text-decoration:underline;color:blue;") 
            messages.success(request, mark_safe(code + f"Successfully printed {link}: {undo_link}"))
            return 

        captcha_img = einvoice_service.captcha()
        img_base64 = base64.b64encode(captcha_img).decode('utf-8')
        return render_confirmation_page("einvoice_login.html",request,queryset,{'image_data': img_base64})

    @admin.action(description="Add to Plain Loading Sheet")
    def add_to_loading_sheet(self, request, queryset):
        return queryset.update(plain_loading_sheet = True)
    
    @admin.action(description="Remove from Plain Loading Sheet")
    def remove_from_loading_sheet(self, request, queryset):
        return queryset.update(plain_loading_sheet = False)

    @admin.action(description="Reload Bill")
    def printed_by_mistake(self, request, qs):
        loading_sheets = list(qs.values_list("loading_sheet",flat=True).distinct())
        qs.update(print_time=None,loading_sheet=None,is_reloaded = True)
        models.SalesmanLoadingSheet.objects.filter(inum__in = loading_sheets).delete()
        return qs.update(print_time = None,is_reloaded = True)

    @admin.action(description="Both Copy")
    def both_copy(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.SECOND_COPY,PrintType.FIRST_COPY])

    @admin.action(description="First Copy")
    def first_copy(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.FIRST_COPY])

    @admin.action(description="Second Copy")
    def second_copy(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.SECOND_COPY])

    @admin.action(description="Double First Copy")
    def double_first_copy(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.DOUBLE_FIRST_COPY])

    @admin.action(description="Salesman Loading Sheet")
    def loading_sheet_salesman(self, request, queryset):

        class SalesmanLoadingSheetForm(forms.Form):
            beat = forms.CharField(required=False,disabled=True,initial=queryset.first().bill.beat)
            party_name = forms.ModelChoiceField(required=False,queryset=models.Party.objects.none(),
                                widget=autocomplete.ModelSelect2(url='admin:print_party_autocomplete',forward=['beat']),
                                label="Party Name")
            Submit = submit_button("Print")
            Action = ""
        
        if "confirm_action" in request.POST : 
            return self.base_print_action(request, queryset, [PrintType.LOADING_SHEET_SALESMAN])
        else  :
            return render_confirmation_page("salesman_loadingsheet.html",request,queryset,
                                            extra_context={"form" : SalesmanLoadingSheetForm(), "show_cancel_btn" : True})

    @admin.action(description="Plain Loading Sheet")
    def loading_sheet(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.LOADING_SHEET])

    @admin.action(description="Only E-Invoice")
    def only_einvoice(self, request, queryset):
        return self.base_print_action(request, queryset, [])
    
    def undo_print(self,request):
        ids = request.GET.get('inums', '')  
        id_list = ids.split(',')
        redirect_url = unquote(request.GET.get('next', ''))

        if "confirm" in request.GET : 
            confirm_undo = bool(request.GET.get("confirm") == "true")
            if confirm_undo : 
                qs = models.Bill.objects.filter(bill_id__in=id_list)
                self.printed_by_mistake(request,qs)
            return redirect(redirect_url)
        else :
            response_text = f"Are you sure that you have printed by mistake for the bills from {id_list[0]} to {id_list[-1]}?"
            confirm_link = f"{request.get_full_path()}&confirm=true"
            cancel_link = f"{request.get_full_path()}&confirm=false"
            return HttpResponse(f"<script>if(confirm('{response_text}')) {{ window.location.href='{confirm_link}'; }} else {{ window.location.href='{cancel_link}'; }}</script>")
          
class RetailPrintAdmin(PrintAdmin) : 
    title = "Retail Bills"
    def get_queryset(self, request):
        return super().get_queryset(request).exclude(bill__beat__contains = "WHOLESALE")
    
class WholeSalePrintAdmin(PrintAdmin) : 
    title = "WholeSale Bills"
    actions = ["double_first_copy"]
    
    @admin.action(description="Double First Copy")
    def double_first_copy(self, request, queryset):
        return self.base_print_action(request, queryset, [PrintType.DOUBLE_FIRST_COPY])

    def get_queryset(self, request):
        return super().get_queryset(request).filter(bill__beat__contains = "WHOLESALE")



class BillDeliveryAdmin(CustomAdminModel) : 
    
    list_display = ["bill_id","party","vehicle_id","loading_time","delivered","delivered_time","is_loading_sheet","bill_date","beat"]
    list_filter = ["vehicle_id","loading_time","delivered_time",
                   create_simple_admin_list_filter("Beat","beat",{
                       "RETAIL" : lambda qs : qs.exclude(bill__beat__contains = "WHOLESALE") ,
                       "WHOLESALE" : lambda qs : qs.filter(bill__beat__contains = "WHOLESALE") ,
                       })]
    
    ordering = ("bill_id",)
    search_fields = ("bill","vehicle_id")
    
    def bill_date(self,obj) : 
        return obj.bill.date 
    
    def party(self,obj) : 
        return obj.bill.party.name

    def beat(self,obj) : 
        return obj.bill.beat
    
    @admin.display(boolean=True,description="LS")
    def is_loading_sheet(self,obj) : 
        return not (obj.loading_sheet is None)
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            queryset = response.context_data['cl'].queryset
            loading_sheets = queryset.filter(loading_sheet__isnull=False).values('loading_sheet').distinct().count()
            single_bills = queryset.filter(loading_sheet__isnull=True).distinct().count()
            response.context_data['cl'].result_count = single_bills+loading_sheets
            #f"SINGLE: {single_bills}, LS: {loading_sheets} = {single_bills+loading_sheets}" 
        except (AttributeError, KeyError):
            pass
        return response
    


class BankCollectionInline(admin.TabularInline) : 
    class BankCollectionForm(forms.ModelForm):
        party  = forms.CharField(label="Party",required=False,disabled=True)
        balance  = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label='Outstanding',disabled=True)
        class Meta:
            model = models.BankCollection
            fields = ["bill","party","balance","amt"]
            widgets = {
                'bill': dal.autocomplete.ModelSelect2(url='/app/chequedeposit/billautocomplete') ,  
                "amt" : forms.TextInput() ,
            }
            
    model = models.BankCollection
    show_change_link = False
    verbose_name_plural = "Collection"
    form = BankCollectionForm
    extra = 1 
    class Media:
        js = ('admin/js/bank_inline.js',)
           
class ChequeDepositAdmin(CustomAdminModel) : 
 
    permissions = [Permission.change,Permission.add,Permission.delete]
    list_display = ["cheque_date","cheque_no","party","amt","bank","deposit_date"]
    autocomplete_fields = ["party"]
    inlines = [BankCollectionInline]
    readonly_fields = ["deposit_date"]
    actions = ['generate_deposit_slip']
    list_filter = [ create_simple_admin_list_filter("Can Be Deposited Today?","cheque_date",{
                       "Yes" : lambda qs : qs.filter(cheque_date__lte = datetime.date.today(),deposit_date__isnull=True) ,
                       "No" : lambda qs : qs.exclude(cheque_date__lte = datetime.date.today(),deposit_date__isnull=True),
                       }, allow_all= False)  ] 
    

    def get_actions(self,request) : 
        actions = super().get_actions(request)
        if "delete_selected" in actions : actions.pop("delete_selected")
        return actions

    def has_change_permission(self, request, obj=None):
        if (obj and hasattr(obj,"bank_entry")) and (obj.bank_entry is not None) : 
            return False 
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)
    
    @admin.action(description="Generate Deposit Slip")
    def generate_deposit_slip(self, request, queryset):
        # Create the deposit slip data
        data = [
            {'S.NO': idx + 1, 'NAME': cheque.party.name, 'BANK': cheque.bank, 'CHEQUE NO': cheque.cheque_no, 'AMOUNT': cheque.amt , 
             'BILLS' : ','.join( cheque.collection.all().values_list("bill__inum",flat=True) ) }
            for idx, cheque in enumerate(queryset)
        ]

        # Create a new Excel file in memory
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=deposit_slip.xlsx'

        with pd.ExcelWriter(response, engine='xlsxwriter') as writer:
            # Convert the cheque data to a DataFrame
            df = pd.DataFrame(data)
            
            # Write the data to the Excel file
            workbook = writer.book
            worksheet = workbook.add_worksheet('DEPOSIT SLIP')

            # Formatting options
            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 14,
                'border': 1
            })

            # Write the header section with merged cells
            worksheet.merge_range('A1:E1', 'DEPOSIT SLIP', header_format)
            worksheet.merge_range('A2:E2', 'DEVAKI ENTERPRISES', header_format)
            worksheet.merge_range('A3:E3', 'A/C NO: 1889223000000030', header_format)
            worksheet.merge_range('A4:E4', 'PAN NO: AAPFD1365C', header_format)
            worksheet.merge_range('A5:E5', f'DATE: {datetime.date.today().strftime("%d %b %Y")}', header_format)

            # Start writing the cheque data below the header
            df_start_row = 5

            # Write column headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(df_start_row, col_num, value,header_format)

            # Write data rows
            for row_num, row_data in enumerate(df.values):
                for col_num, cell_value in enumerate(row_data):
                    worksheet.write(df_start_row + row_num + 1, col_num, cell_value)

            # Save the worksheet
            writer.sheets['DEPOSIT SLIP'] = worksheet

        # Update the queryset to set the deposit date
        queryset.update(deposit_date=datetime.date.today()) 

        return response

    ##Outstanding Bill autocomplete 
    class BillAutocomplete(autocomplete.Select2QuerySetView):
        def get_queryset(self):
            qs = models.Outstanding.objects.all().filter(balance__lte = -1)
            if self.q:
                qs = qs.filter(Q(inum__icontains=self.q) | Q(party__name__icontains=self.q)) 
            return qs
    
    #To fix unpushed collection for the current bank collection (cheque + neft)
    ##Custom view to support fetch outstanding in inlines 
    def get_outstanding(self,request, inum):
        try:
            obj = models.Outstanding.objects.get(inum=inum.split("-")[0])
            unpushed_coll = models.BankCollection.objects.filter(bill_id = inum,pushed = False).aggregate(Sum("amt"))["amt__sum"] or 0
            return JsonResponse({'balance': str(round(-obj.balance,2)) , 'party' : obj.party.name , 'unpushed_coll' :  unpushed_coll})
        except models.Outstanding.DoesNotExist:
            return JsonResponse({'balance': 0,'party': '-',"unpushed_coll" : 0})

    custom_views = [("get-outstanding/<str:inum>","get_outstanding"),("billautocomplete",BillAutocomplete.as_view())]


    def response_add(self, request, obj, post_url_continue=None):
        ##Override parent function to prevent chnage success message when the bank collection is not valid 
        if obj.is_valid : 
            return super().response_add(request, obj)
        else : 
            # return redirect(request.get_full_path())
            return self.response_post_save_add(request, obj)

    def response_change(self, request, obj): # type: ignore
        ##Override parent function to prevent chnage success message when the bank collection is not valid 
        if obj.is_valid : 
            return super().response_change(request, obj)
        else : 
            # return redirect(request.get_full_path())
            return self.response_post_save_change(request, obj)

    def save_model(self, request, obj, form, change):
        obj._save_deferred = True  # Flag to save it later in save_related()

    def save_related(self, request, form, formsets , change):
        bank_obj = form.instance 
        total_amt = 0 
        for formset in formsets:
            if formset.model == models.BankCollection  :
                for inline_form in formset.forms:
                    obj = inline_form.instance
                    is_deleted = inline_form.cleaned_data.get('DELETE')
                    if obj.amt and (not is_deleted):
                        total_amt += obj.amt    

        if abs(total_amt - bank_obj.amt) > 5 :  
            messages.error(request,f"Cheque Value & Collection Value Mismatch \n Total value : {total_amt} , Cheque amt : {bank_obj.amt}")
            bank_obj.is_valid = False 
            formsets.clear()
            return 
        else : 
            bank_obj.is_valid = True 
            if hasattr(form.instance, '_save_deferred') and form.instance._save_deferred:
              super().save_model(request,bank_obj,form,change)    
        super().save_related(request,form,formsets, change)

class NoSelectActions(admin.ModelAdmin) : 
      empty_actions = []
      def changelist_view(self, request: HttpRequest, extra_context: Dict[str, str] | None = ...) -> TemplateResponse:
          if request.POST.get("action") in self.empty_actions :
             post = request.POST.copy()
             post.update({ "_selected_action" : [] })
             request._set_post(post)
          return super().changelist_view(request, extra_context)
      
class BankStatementAdmin(CustomAdminModel,NoSelectActions) : 

    change_list_template = "form_and_changelist.html"
    list_display = ["date","ref","desc","amt","bank","saved","type","id"]
    readonly_fields = ["amt","desc","date","ref","bank","idx","id"]
    hidden_fields = ["idx"]
    list_filter = ["date","type","bank"]
    # search_fields = ["amt","desc"]
    list_display_links = ["date","amt"]
    ordering = ["-date"]
    permissions = [Permission.change,Permission.delete]
    actions = ["auto_match_statement","refresh_collection"]
    empty_actions = ["auto_match_statement","refresh_collection"]
    # change_form_template = "admin/bankstatement_change_form.html"

    def get_actions(self,request) : 
        actions = super().get_actions(request)
        if "delete_selected" in actions : actions.pop("delete_selected")
        return actions

    @admin.display(boolean=True)
    def saved(self,obj) : 
        return obj.type is not None
     
    class NeftCollectionInline(BankCollectionInline) : 
        verbose_name_plural = "NEFT Collection"
        def get_queryset(self, request):
            queryset = super().get_queryset(request)
            queryset = queryset.filter(cheque_entry__isnull=True)
            return queryset
    
    #Not used (for future uses)
    class IkeaCollectionInline(admin.TabularInline) : 
        model = models.Collection
        verbose_name_plural = "IKEA Pushed Collection"
    
    @admin.action(description="Refresh Ikea Collection")
    def refresh_collection(self,request,qs) : 
        sync_reports(limits={"collection":None},min_days_to_sync={"collection":7})

    @admin.action(description="Auto Match Statement")
    def auto_match_statement(self,request,qs) :
        qs = models.BankStatement.objects.filter(date__gte = datetime.date.today() - datetime.timedelta(days=7)) 
        qs.filter(Q(desc__icontains="cash") & Q(desc__icontains="deposit")).update(type="cash_deposit")
        qs = qs.filter(Q(type__isnull=True)|Q(type="upi"))
        fromd = qs.aggregate(Min("date"))["date__min"]
        tod = qs.aggregate(Max("date"))["date__max"]
        upi_statement:pd.DataFrame = IkeaDownloader().upi_statement(fromd - datetime.timedelta(days = 3),tod)
        upi_statement["FOUND"] = "No"
        upi_statement["PAYMENT ID"] = upi_statement["PAYMENT ID"].astype(str).str.split(".").str[0]
        for bank_obj in qs.all() : 
            for _,row in upi_statement.iterrows() : 
                if (row["FOUND"] == "No") and (row["PAYMENT ID"] in bank_obj.desc) : 
                    bank_obj.type = "upi"
                    bank_obj.save()
                    upi_statement.loc[_,"FOUND"] = "Yes"
                    
        upi_during_period = upi_statement[(upi_statement["COLLECTED DATE"].dt.date >= fromd)] 
        upi_before_period = upi_statement[(upi_statement["COLLECTED DATE"].dt.date < fromd)] 

        with pd.ExcelWriter("UPI Matching.xlsx") as writer :
            upi_during_period[upi_during_period["FOUND"] == "No"].to_excel(writer,sheet_name="Un-Matched UPI (Current)",index=False)
            upi_during_period[upi_during_period["FOUND"] == "Yes"].to_excel(writer,sheet_name="Matched UPI (Current)",index=False)
            upi_before_period[upi_before_period["FOUND"] == "Yes"].to_excel(writer,sheet_name=f"Matched UPI (Before)",index=False)
        
        link = hyperlink(f"/static/UPI Matching.xlsx",f"Download UPI Matching",style="text-decoration:underline;color:blue;") 
        messages.success(request,mark_safe(link))

    def get_inlines(self, request, obj = None):
        if self.has_change_permission(request,obj) : 
            return [self.NeftCollectionInline]
        else : 
            return [self.NeftCollectionInline,self.IkeaCollectionInline]

    def has_change_permission(self, request, obj=None):
        if obj and (obj.collection.filter(pushed = True).count()) :
                return False 
        return super().has_change_permission(request, obj)
    
    # def has_delete_permission(self, request, obj=None):
    #     if obj and obj.ikea_collection.count() : 
    #         return False 
    #     return super().has_delete_permission(request, obj)
    
    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        models.BankCollection.objects.filter(bank_entry = obj).update(pushed = False)
        models.BankCollection.objects.filter(bank_entry = obj,cheque_entry__isnull = False).update(bank_entry = None)
        return super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            old_obj = models.BankStatement.objects.get(pk=obj.pk)

            if (old_obj.type != obj.type) or (old_obj.type == "cheque") : 
                if old_obj.type == "cheque" :  
                    models.BankCollection.objects.filter(bank_entry = old_obj).update(bank_entry = None)
                if old_obj.type == "neft" : 
                    models.BankCollection.objects.filter(bank_entry = old_obj).delete()

            if obj.type == "cheque" : 
                models.BankCollection.objects.filter(cheque_entry = obj.cheque_entry).update(bank_entry = obj)

        if (obj.type != "cheque") : 
            obj.cheque_entry = None

        super().save_model(request, obj, form, change)
       
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "cheque_entry":
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                bank_entry = models.BankStatement.objects.get(pk=obj_id)
                kwargs["queryset"] = models.ChequeDeposit.objects.filter(
                    amt__gte=bank_entry.amt - 10,
                    amt__lte=bank_entry.amt + 10
                ).filter( Q(bank_entry__isnull=True) | Q(bank_entry = bank_entry) )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def changelist_view(self, request, extra_context:dict ={}): # type: ignore

        class BankStatementUploadForm(forms.Form):
            # bank = forms.ChoiceField(choices=(("sbi","SBI"),("kvb","KVB")),initial="sbi")
            excel_file = forms.FileField(label="Bank Statement Excel")
            Submit = submit_button("Upload")
            Action = ""

        if request.method == 'GET' :
            sync_reports(limits = {"collection":10*60})

        form = BankStatementUploadForm()
        if request.method == 'POST' and (request.POST.get("action") is None):
            form = BankStatementUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['excel_file']
                bank_name = "sbi" if excel_file.name.endswith("xls") else "kvb" #form.cleaned_data["bank"]
                df = pd.DataFrame()
 
                def skiprows_excel(excel_file,col_name,col_number,sep) : 
                    df = pd.read_csv(excel_file , skiprows=0 , sep=sep , names = list(range(0,100)) , header = None)
                    skiprows = -1 
                    acc_no = None 
                    for i in range(0,20) : 
                        if df.iloc[i][col_number] == col_name : 
                            skiprows = i 
                            break
                        x = df.iloc[i][0]
                        if (type(x) == str) and ("account number" in x.lower()) :
                            acc_no = df.iloc[i][1]
                    df.columns = df.iloc[skiprows]
                    df = df.iloc[skiprows+1:]
                    return df,acc_no 
                
                ACC_BANKS = {"_00000042540766421":"SBI OD",'="1889135000001946"':"KVB CA","_00000042536033659":"SBI CA"}
                acc = None 

                if bank_name == "sbi" : 
                    df,acc = skiprows_excel(excel_file,"Txn Date",col_number=0,sep = "\t")
                    df = df.rename(columns={"Txn Date":"date","Credit":"amt","Ref No./Cheque No.":"ref","Description":"desc"})
                    df = df.iloc[:-1]
                    df["date"] = pd.to_datetime(df["date"],format='%d %b %Y')

                if bank_name == "kvb" : 
                    df,acc = skiprows_excel(excel_file,"\tTransaction Date",col_number=1,sep = ",")
                    df = df.rename(columns={"\tTransaction Date":"date","Credit":"amt","Cheque No.":"ref","Description":"desc"})
                    df["date"] = pd.to_datetime(df["date"],format='%d-%m-%Y %H:%M:%S')
                    df = df.sort_values("date")
                    df["ref"] = df["ref"].astype(str).str.split(".").str[0]

                if acc and (acc in ACC_BANKS) :
                    bank_name = ACC_BANKS[acc]
                else : 
                    raise Exception(f"Bank acc no : {acc} doesn't have a bank")

                df["idx"] = df.groupby(df["date"].dt.date).cumcount() + 1 
                df = df[["date","ref","desc","amt","idx"]]
                df["bank"] = bank_name 
                free_ids = list(set(range(100000,999999)) - set(query_db("SELECT CAST(id as INT) as id FROM app_bankstatement",is_select=True)["id"]))
                df["id"] = pd.Series(free_ids[:len(df.index)],index=df.index)
                # df["id"] = (lambda date, number: (( 10*bank_index + (date.dt.year - 2020)) * 12 * 31  + date.dt.month * 31  + date.dt.day) * 100 + number)(df.date,df.idx).astype(str)
                df["date"] = df["date"].dt.date
                print( df )
                df = df[df.amt != ""][df.amt.notna()]
                df.amt = df.amt.astype(str).str.replace(",","").apply(lambda x  : float(x.strip()) if x.strip() else 0)
                df = df[df.amt != 0]
                print( df )
                bulk_raw_insert("bankstatement",df,ignore=True)
                messages.success(request, "Statement successfully uploaded")
            else : 
                messages.error(request, "Statement upload failed")
        extra_context['form'] = form
        return super().changelist_view(request, extra_context=extra_context | {"title" : ""})

    def _delete_view(self, request, object_id, extra_context):
        billing = IkeaDownloader()
        qs = models.BankCollection.objects.filter(bank_entry_id = object_id)
        if qs.count() : 
            bill_chq_pairs = [ (bank_coll.bank_entry_id,bank_coll.bill_id) for bank_coll in qs.all() ]
            dates = models.BankStatement.objects.filter(id = object_id).aggregate(
                                fromd = Min("ikea_collection__date"), tod = Max("ikea_collection__date"))
            settle_coll:pd.DataFrame = billing.download_settle_cheque("ALL",dates["fromd"],dates["tod"]) # type: ignore
            settle_coll = settle_coll[ settle_coll.apply(lambda row : (str(row["CHEQUE NO"]),row["BILL NO"]) in bill_chq_pairs ,axis=1) ]
            settle_coll["STATUS"] = "BOUNCED"
            f = BytesIO()
            settle_coll.to_excel(f,index=False)
            f.seek(0)
            res = billing.upload_settle_cheque(f)
            qs.update(pushed = False)
            sync_reports(limits = {"collection" : None})

        return redirect(request.get_full_path().replace("delete","change"))

class BankCollectionAdmin(CustomAdminModel) : 

    list_display = ["bill","party","amt","type","cheque_no","pushed"]
    permissions = [Permission.delete]
    actions = ["push_collection","recheck_pushed_coll"]
    list_filter = ["pushed"]
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def party(self,obj) : 
        return obj.bill.party 
    
    def cheque_no(self,obj) :
        c = obj.cheque_entry 
        return  c.cheque_no if c else None 

    def type(self,obj) : 
        return obj.bank_entry.type if obj.bank_entry else "-"
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(bank_entry__isnull = False).exclude(bank_entry__cheque_status = "bounced")
    
    @admin.action(description="Re-Check Pushed Collection")
    def recheck_pushed_coll(self, request, queryset):
        sync_reports(limits = {"collection":None}, min_days_to_sync= {"collection":10})
        for obj in queryset :    
            pushed = models.Collection.objects.filter(bank_entry_id = obj.bank_entry_id,bill_id = obj.bill_id).exists() 
            obj.pushed = pushed
            obj.save()
            
    @admin.action(description="Push Collection")
    def push_collection(self, request, queryset):

        queryset = queryset.filter(pushed = False,bank_entry__isnull = False)
        billing = Billing()
        coll:pd.DataFrame = billing.download_manual_collection() # type: ignore
        manual_coll = []
        bill_chq_pairs = []
        for coll_obj in queryset.all() : 
            bank_obj = coll_obj.bank_entry 
            bill_no  = coll_obj.bill_id 
            row = coll[coll["Bill No"] == bill_no].copy()
            row["Mode"] = "Cheque/DD" #("Cheque/DD" if bank_obj.type == "cheque" else "NEFT") ##Warning
            row["Retailer Bank Name"] =  coll_obj.cheque_entry.bank.upper() if coll_obj.cheque_entry else "KVB 650" 	
            row["Chq/DD Date"]  = bank_obj.date.strftime("%d/%m/%Y")
            chq_no = bank_obj.id 
            row["Chq/DD No"] = chq_no
            row["Amount"] = coll_obj.amt
            manual_coll.append(row)
            bill_chq_pairs.append((chq_no,bill_no))

        manual_coll = pd.concat(manual_coll)
        manual_coll["Collection Date"] = datetime.date.today()

        f = BytesIO()
        manual_coll.to_excel(f,index=False)
        f.seek(0)
        res = billing.upload_manual_collection(f)

        cheque_upload_status = pd.read_excel(billing.download_file(res["ul"]))
        cheque_upload_status.to_excel("cheque_upload_status.xlsx")
        sucessfull_coll = cheque_upload_status[cheque_upload_status["Status"] == "Success"]

        settle_coll:pd.DataFrame = billing.download_settle_cheque() # type: ignore
        if "CHEQUE NO" not in settle_coll.columns : 
            link = hyperlink(f"/static/cheque_upload_status.xlsx",f"Download Ikea Push Summary",style="text-decoration:underline;color:blue;") 
            messages.error(request,mark_safe(link))
            return 

        settle_coll = settle_coll[ settle_coll.apply(lambda row : (str(row["CHEQUE NO"]),row["BILL NO"]) in bill_chq_pairs ,axis=1) ]
        settle_coll["STATUS"] = "SETTLED"
        f = BytesIO()
        settle_coll.to_excel(f,index=False)
        f.seek(0)
        res = billing.upload_settle_cheque(f)

        bytes_io = billing.download_file(res["ul"])
        cheque_settlement = pd.read_excel(bytes_io)
        cheque_settlement.to_excel("cheque_settlement.xlsx")
        for _,row in sucessfull_coll.iterrows() : 
            chq_no = row["Chq/DD No"]
            bill_no = row["BillNumber"]
            models.BankCollection.objects.filter(bank_entry_id = chq_no,bill_id = bill_no).update(pushed = True)

        sync_reports(limits = {"collection" : None})
        with pd.ExcelWriter(open("push_cheque_ikea.xlsx","wb+"), engine='xlsxwriter') as writer:
            cheque_upload_status.to_excel(writer,sheet_name="Manual Collection")
            cheque_settlement.to_excel(writer,sheet_name="Cheque Settlement")

        link = hyperlink(f"/static/push_cheque_ikea.xlsx",f"Download Ikea Push Summary",style="text-decoration:underline;color:blue;") 
        messages.success(request,mark_safe(link))
                       
    def changelist_view(self, request: HttpRequest, extra_context = {}) -> TemplateResponse:
        return super().changelist_view(request, {"title" : "Push Pending Collection to IKEA"} | extra_context)
    
ProcessStatus = IntEnum("ProcessStatus",(("NotStarted",0),("Success",1),("Started",2),("Failed",3)))

class BasepackAdmin(BaseProcessStatusAdmin) : 
    
    basepack_lock = threading.Lock()

    change_list_template = "form_and_changelist.html"
    process_logs = []
    process_names = ["current_stock","basepack_download","basepack_upload","beat_export","order_sync"]
                

    def current_stock(self,ikea,form) : 
        stock = ikea.current_stock(datetime.date.today() )
        print( stock )
        stock = stock[stock.Location == "MAIN GODOWN"]
        self.active_basepack_codes = list(set(stock["Basepack Code"].dropna().astype(int))  )
        self.current_stock_original = stock.copy()
    
    def basepack_download(self,ikea,form) : 
        self.basepack_io = ikea.basepack()         
    
    def basepack_upload(self,ikea,form) : 
        with open("a.xlsx","wb+") as f : f.write(self.basepack_io.getvalue())
        wb = load_workbook(self.basepack_io , data_only = True)
        sh = wb['Basepack Information']
        rows = sh.values
        basepack = pd.DataFrame( columns=next(rows) , data = rows )
        basepack_original = basepack.copy()
        color_in_hex = [cell.fill.start_color.index for cell in sh['A:A']]
        basepack["color"] = pd.Series( color_in_hex[1:])
        basepack = basepack[ basepack["color"] != 52 ][basepack["BasePack Code"].notna()]
        basepack["new_status"] = basepack["BasePack Code"].isin([ str(code) for code in self.active_basepack_codes ])
        basepack = basepack[ basepack["new_status"] != (basepack["Status"] == "ACTIVE") ]
        basepack.to_excel("basepack.xlsx",index=False,sheet_name="Basepack Information")      
        basepack["Status"] = basepack["Status"].replace({ "ACTIVE" : "INACTIVE_x" , "INACTIVE" : "ACTIVE_x" })
        basepack["Status"] = basepack["Status"].str.split("_").str[0] 
        basepack = basepack[ list(basepack.columns)[5:11] ]
        basepack = basepack.astype({"BasePack Code":str,"SeqNo":int,"MOQ":int})


        output = BytesIO()
        writer = pd.ExcelWriter(output,engine='xlsxwriter')
        basepack.to_excel(writer,index=False,sheet_name="Basepack Information")
        basepack_original.to_excel(writer,index=False,sheet_name="basepack_original")
        self.current_stock_original.to_excel(writer,index=False,sheet_name="currentstock")
        writer.close()
        output.seek(0)

        print( "Basepack Changed (NEW STATUS COUNTS) : " ,  basepack["Status"].value_counts().to_dict() )
        with open('basepack.xlsx', 'wb+') as f:  
            f.write(output.read())
        
        if len(basepack.index) : 
            output.seek(0)
            files = { "file" : ("basepack.xlsx", output ,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')  }
            res = ikea.post("/rsunify/app/basepackInformation/uploadFile", files = files ).text 
            print( res )
            print("Basepack uploaded") 
        else : 
            print("Nothing to upload basepack")

    def beat_export(self,ikea,form) : 
        ##Start Beat Export and Order Sync after basepack uploaded
        today = datetime.date.today() 
        export_data = { "fromDate": str(today) ,"toDate": str(form.cleaned_data["date"]) }
        ikea.post("/rsunify/app/quantumExport/checkBeatLink",
                data = {'exportData': json.dumps(export_data) })
        ikea.post("/rsunify/app/sfmIkeaIntegration/callSfmIkeaIntegrationSync")
        ikea.post("/rsunify/app/sfmIkeaIntegration/checkEmpStatus")
        sm = ikea.post("/rsunify/app/quantumExport/getSalesmanData", 
                data={"exportData": json.dumps(export_data) }).json()
        sm = ",".join( i[0]  for i in sm )
        ikea.post("/rsunify/app/ikeaCommonUtilController/qocRepopulation")
        export_num = ikea.post("/rsunify/app/quantumExport/startExport",
                    data = {"exportData": json.dumps(export_data | {"salesManId": sm ,"beatId":"-1"}) } ).json()
        for i in range(60) : 
            status = ikea.post("/rsunify/app/quantumExport/getExportStatus",{"processId": export_num}).json()
            if str(status) == str(["0","0","1"]) : #comparing two lists
                print("Beat Export Completed")
                return 
            time.sleep(5)
            ikea.logger.debug(f"Waiting for beat export to be completed")
        raise Exception("Beat Export Timed Out After 5 Minutes")

    def order_sync(self,ikea,form) : 
        ikea.post("/rsunify/app/sfmIkeaIntegration/callSfmIkeaIntegrationSync")
        ikea.post("/rsunify/app/api/callikeatocommoutletcreationallapimethods")
        sync_status = ikea.post("/rsunify/app/fileUploadId/upload").text.split("$del")[0]
        ikea.logger.debug(f"Order Sync (Basepack) status : {sync_status}")
        
    def basepack(self,form) :
        with self.basepack_lock : 
            ikea = Billing()
            processes = [self.current_stock,self.basepack_download,self.basepack_upload,self.beat_export,self.order_sync]
            processes = [ functools.partial(process,ikea,form) for process in processes ]
            self.run_processes(processes)
                    
    def changelist_view(self, request: HttpRequest, extra_context:dict = {}) -> TemplateResponse: # type: ignore
        today = datetime.date.today()

        def get_default_beat_export_date() :
            days = 6 
            return  (today + datetime.timedelta(days=days)) if (today.day <= (20 - days)) or (today.day > 20) else today.replace(day=20)
        
        class BasepackForm(forms.Form) : 
            date = forms.DateField(required=False,initial=get_default_beat_export_date(),
                                   label="Beat Export Date", widget=forms.DateInput(attrs={'type' : 'date'}),disabled=True)
            Submit = submit_button("Submit")
            download = submit_button("Download")
            Action = ""

        form = BasepackForm()
        if request.method == "POST" :     
            form = BasepackForm(request.POST)
            if form.is_valid() :
                if form.cleaned_data.get("download") :
                    with open("basepack.xlsx","rb") as f : 
                        bytes = f.read()
                    response = HttpResponse(bytes, content_type='application/vnd.ms-excel')
                    response['Content-Disposition'] = 'attachment; filename="' + f"basepack_{today}.xlsx" + '"'
                    return response 
                                
                if not self.basepack_lock.locked() : 
                    self.create_logs()
                    thread = threading.Thread( target = self.basepack , args = (form,) )
                    thread.start()
        else : 
            if not self.basepack_lock.locked() :  
                models.BasepackProcessStatus.objects.all().delete()     
        refresh_time = 20000 if self.basepack_lock.locked() else 1e7 
        return super().changelist_view(request, extra_context | {"refresh_time" : refresh_time , "form" : form, "title" : "" })

class SalesmanPendingSheetAdmin(CustomAdminModel) :
     
    change_list_template = "form_and_changelist.html"
    list_display =  ["name","salesman_name","days"]
    actions = ["download_pending_sheet"]
    list_filter = [ create_simple_admin_list_filter("Beat Day","days", { key: functools.partial(lambda days,qs: 
                    qs.filter(days__contains = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%A").lower() ) , no_of_days) 
                    for key,no_of_days in [("Today",0),("Tommorow",1),("Day after Tommorow",2)] })]

    @admin.action(description='Download Pending Sheet')
    def download_pending_sheet(self,request,queryset) :
        date = request.POST.get("date",None)
        if date is None : #selected beats case (no date supplied)
            # Find the date that is greater than today and whose day is equal to the given day.
            day = queryset.exclude(days__contains=",").first().days
            today = datetime.date.today()
            day_to_index = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
            if day :
                date = today + datetime.timedelta(days = (day_to_index.index(day) - today.weekday()) % 7)
            else : 
                date = today + datetime.timedelta(days = 1)
        else : 
            date = datetime.datetime.strptime(date,"%Y-%m-%d").date()
        print( "Pending Sheet On Date : " , date )
        beat_ids = { str(id) for id in queryset.values_list("id",flat=True) }
        beat_maps = { beat.name : (beat.salesman_name,beat.id) for beat in queryset.all() }
        billing = Billing()
        bytesio = billing.pending_statement_excel(beat_ids,date - datetime.timedelta(days=1)) #Dont consider bills on the same date
        df = pd.read_excel(bytesio,skiprows = 13,skipfooter=1)
        df = df.dropna(subset = "Beat Name")
        df["Salesperson Name"] = df["Salesperson Name"].str.split("-").str[1]
        pdfs = [] 
        for beat , rows in df.groupby("Beat Name") : 
            max_days_per_party = rows.groupby("Party Name")["Bill Ageing (In Days)"].max().to_dict()
            rows["max_days_per_party"] = rows["Party Name"].map(max_days_per_party)
            rows = rows.sort_values(by = ["max_days_per_party","Party Name"] , ascending=False)
            salesman,beat_id = beat_maps[beat]
            sheet_no = "PS" + date.strftime("%d%m%y") + str(beat_id)
            # models.PendingSheetBill.objects.filter(sheet_id = sheet_no).delete()
            models.PendingSheet(sheet_no=sheet_no,beat=beat,salesman=salesman,date=date).save()
            rows["sheet_id"] = sheet_no 
            renamed_rows = rows.rename(columns={"Bill No":"bill_id","OutstANDing Amount":"outstanding_amt","Bill Ageing (In Days)" : "days"})
            bulk_raw_insert("pendingsheetbill",renamed_rows[["sheet_id","bill_id","days","outstanding_amt"]],ignore=True)
            bytesio = pdf_create.pending_sheet_pdf(rows , sheet_no ,  salesman , beat , date)
            pdfs.append(bytesio)
        
        writer = PdfWriter()
        for pdf in pdfs :
            reader = PdfReader(pdf)
            for page in reader.pages:
                writer.add_page(page)
            if len(reader.pages) % 2 != 0:
                writer.add_blank_page()
        writer.write("pending_sheet.pdf")
        writer.close()
            
        messages.success(request,mark_safe(f"Download Pending Sheet : {hyperlink('/static/pending_sheet.pdf','PENDING_SHEET')}"))
            
    def changelist_view(self, request, extra_context = {}) : 
        class PendingSheetForm(forms.Form) : 
            date = forms.DateField(initial=datetime.date.today() + datetime.timedelta(days = (datetime.datetime.now().hour > 3)) ,
                                    widget=forms.DateInput(attrs={'type' : 'date'}))
            beat_type = forms.ChoiceField(choices=(("Retail","Retail"),("Wholesale","Wholesale")),initial="Retail")
            Submit = submit_button("Download")

        form = PendingSheetForm()
        if request.method == "POST" : 
            if "Submit" in request.POST : 
                form = PendingSheetForm(request.POST)
                if form.is_valid() : 
                    qs = self.model.objects.filter(days__contains = form.cleaned_data["date"].strftime("%A").lower())
                    print( list(qs) )
                    print( qs.values_list("salesman_name",flat=True))
                    print( qs.values_list("name",flat=True) )
                    if form.cleaned_data["beat_type"] == "Retail" : 
                        qs = qs.exclude(name__contains = "WHOLESALE")
                    else :
                        qs = qs.filter(name__contains = "WHOLESALE")
                    self.download_pending_sheet(request,qs)



        return super().changelist_view(request, extra_context | {"form" : form,"title":"",
                                                                 "form_style":"margin-bottom:50px;border:2px solid"})
    
class SettingsAdmin(CustomAdminModel) :
    permissions = [Permission.change,Permission.add]
    list_display_links = ["key"]
    list_display = ["key","status","value"]
    list_editable = ["status","value"]


query_url = lambda view,params : f'{reverse(view)}?{urlencode(params)}'

class MyAdminSite(admin.AdminSite):

    models_on_navbar = []
    site_title = "Devaki Enterprises"
    
    def get_app_list(self, request,app_label=None):
        """
        Return a sorted list of all the installed apps that have been registered
        in this admin site, excluding certain models.
        """
        app_list = super().get_app_list(request,app_label)
        for app in app_list:
            models = [ model_dictionary for model_dictionary in app["models"] if model_dictionary["model"] in self.models_on_navbar ]
            models = sorted(models,key = lambda model_dict : self.models_on_navbar.index(model_dict["model"]))
            app["models"] = models
        return app_list
    
    def register(self, model_or_iterable, admin_class = None, show_on_navbar = True,options = {}):
        super().register(model_or_iterable, admin_class, **options)
        if not isinstance(model_or_iterable,Iterable) : model_or_iterable = [model_or_iterable,]
        for model in model_or_iterable : 
            if show_on_navbar : self.models_on_navbar.append(model)

    def each_context(self, request):
        context = super().each_context(request)
        navbar_data = {
            "Billing": reverse("admin:app_orders_changelist") ,
            "Print": {
                "RETAIL": query_url("admin:app_retailprint_changelist" , {"printed":"Not Printed","_facets":"True","bill__date":"Today"}),
                "WHOLESALE": query_url("admin:app_wholesaleprint_changelist" , {"printed":"Not Printed","_facets":"True","bill__date":"Today"}),
            },
            "Collection": {
                "Outstanding": reverse("admin:app_outstanding_changelist"),
                "Salesman Cheque": query_url("admin:app_salesmancollection_changelist" , {"time":"Today"}),
                "Pending Sheet": query_url("admin:app_salesmanpendingsheetx_changelist" , {"date":"Today"}),
            },
            "Cheque" : {
                "Cheque Deposit": reverse("admin:app_chequedeposit_changelist"),
                "Bank Statement": reverse("admin:app_bankstatement_changelist"),
                "Push To Ikea" : query_url("admin:app_bankcollection_changelist" , {"pushed__exact":"0"})
            },
            "Others": {
                "Beat Export": reverse("admin:app_basepackprocessstatus_changelist"),
                "Scan": reverse("scan_bills"),
                "Bill Out": reverse("admin:app_todaybillout_changelist"),
                "Bill In": reverse("admin:app_todaybillin_changelist"),
            },
            "Config": {
                "Vehicle": reverse("admin:app_vehicle_changelist"),
            },
            "Restart": reverse("reload_server") ,
            "Sync": {
                "Sales":"/force-sales-sync" ,
                "Collection":"/force-collection-sync" ,
            }
        }
        context['navbar_data'] = navbar_data
        return context

class TodayOut(CustomAdminModel) :

    change_list_template = "form_and_changelist.html"
    list_display_links = [] 
    list_display = ["vehicle","bills","loading_sheet","total","beats"]
    field = "loading_time"
    title = "Bill Out From Godown"

    def vehicle(self,obj) : 
        today = datetime.datetime.combine(self.date , datetime.datetime.min.time())
        tommorow = datetime.datetime.combine(self.date + datetime.timedelta(days=1), datetime.datetime.min.time())
        return mark_safe(hyperlink(
            query_url("admin:app_billdelivery_changelist" , { "vehicle_id__name__exact":obj.name,f"{self.field}__gte": str(today),
                                                             f"{self.field}__lt": str(tommorow) }), obj.name))

    def get_bills_queryset(self,vehicle) : 
        return models.Bill.objects.filter(**{ f"{self.field}__date" : self.date,"vehicle" : vehicle })
    
    def bills(self,obj) : 
        return self.get_bills_queryset(obj).filter(loading_sheet__isnull=True).count()
    
    def loading_sheet(self,obj) : 
        return self.get_bills_queryset(obj).filter(loading_sheet__isnull=False).values_list(
                                                    "loading_sheet",flat=True).distinct().count()
    
    def beats(self,obj) :
        b = self.get_bills_queryset(obj).values_list("bill_id",flat=True)
        c = models.Sales.objects.filter(inum__in = b).values("beat").annotate(n = Count("inum")).order_by("-n").values_list("beat","n")
        return mark_safe("</br>".join([ f"{i[0]} : {i[1]}" for i in c]))
    
    def total(self,obj) : 
        return self.bills(obj) + self.loading_sheet(obj)
    
    def changelist_view(self, request, extra_context=None):    
        class DateForm(forms.Form) :
            date = forms.DateField(required=True,widget=forms.DateInput(attrs={'type' : 'date'}))
            Submit = submit_button("Submit")
        self.date = datetime.date.today() 
        form = DateForm(request.POST)
        if form.is_valid() :  self.date = form.cleaned_data["date"]
        return super().changelist_view(request, (extra_context or {})| {"title" : self.title, "form" : DateForm(initial = {"date":self.date}) })
    
class TodayIn(TodayOut) :
    list_display = ["vehicle","total_in","total_out","pending_bills"]
    field = "delivered_time"
    title = "Bill In To Godown"

    def total_in(self,obj) : 
        return self.total(obj)
    
    def total_out(self,obj) :
        temp = (self.date,self.field)
        last_loading = models.BillDelivery.objects.exclude(loading_time__date = self.date).order_by("-loading_time").first()
        self.date = last_loading.loading_time.date() if last_loading else (self.date - datetime.timedelta(days=1)) # type: ignore
        self.field = "loading_time"
        total = self.total(obj)
        self.date , self.field = temp 
        return total 
    
    def pending_bills(self,obj) :
        return self.total_out(obj) - self.total_in(obj)
    


admin_site = MyAdminSite(name='myadmin')
# admin_site.has_permission = lambda r: setattr(r, 'user', AccessUser()) or True # type: ignore

admin_site.register(models.Party,PartyAdmin)

admin_site.register(models.Orders,BillingAdmin)
admin_site.register(models.Outstanding,OutstandingAdmin)

admin_site.register(models.ChequeDeposit,ChequeDepositAdmin)
admin_site.register(models.BankStatement,BankStatementAdmin)
admin_site.register(models.BankCollection,BankCollectionAdmin)

admin_site.register(models.SalesmanCollection,SalesCollectionAdmin)

admin_site.register(models.Bill,PrintAdmin)
admin_site.register(models.RetailPrint,RetailPrintAdmin)
admin_site.register(models.WholeSalePrint,WholeSalePrintAdmin)

admin_site.register(models.BillDelivery,BillDeliveryAdmin)

admin_site.register(models.OrdersProxy,OrdersAdmin)
admin_site.register(models.BasepackProcessStatus,BasepackAdmin)
admin_site.register(models.SalesmanPendingSheetX,SalesmanPendingSheetAdmin)
admin_site.register(models.Vehicle,None)
admin_site.register(models.SalesmanLoadingSheet,None)
admin_site.register(models.Settings,SettingsAdmin)

admin_site.register(models.TodayBillOut,TodayOut)
admin_site.register(models.TodayBillIn,TodayIn)


# admin_site.register(models.Eway,EwayAdmin)
