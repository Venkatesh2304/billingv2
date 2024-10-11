from collections import defaultdict
import datetime
from io import BytesIO
import logging
import multiprocessing
import os
import re
import shutil
from threading import Thread
import threading
import time
import traceback
from typing import Any, Dict, Optional, Type
from django import forms
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
import numpy as np
import pandas as pd
from app.common import both_insert, bulk_raw_insert, query_db
import app.models as models 
from django.utils.html import format_html
from django.contrib.admin.templatetags.admin_list import register , result_list  
from django.contrib.admin.templatetags.base import InclusionAdminNode
from custom.Session import Logger  
from custom.classes import Billing,IkeaDownloader
from django.utils import timezone
from django.db.models import Max,F,Subquery,OuterRef,Q,Min,Sum,Count
from django.contrib.admin import helpers, widgets
from collections import namedtuple
from app.sales_import import AdjustmentInsert, CollectionInsert, SalesInsert
from django.urls import path
from django.contrib import messages
import dal.autocomplete
from django.contrib.admin.actions import delete_selected
from pytz import timezone
from custom.Session import client
import app.loading_sheet as loading_sheet

def user_permission(s,*a,**kw) : 
    if a and False : return False #or "add" in a[0] "change" in a[0] or ("add" in a[0] ) 
    return True

class AccessUser(object):
    has_module_perms = has_perm = __getattr__ = user_permission

admin_site = admin.AdminSite(name='myadmin')
admin_site.has_permission = lambda r: setattr(r, 'user', AccessUser()) or True


# logger = Logger("main", logging.DEBUG)
# os.makedirs("logs/files", exist_ok=True)
# formatter = logging.Formatter("%(message)s")
# file_handler = logging.FileHandler(f"logs/main.html", mode="a")
# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)

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

def check_last_sync(model_class,limit) :
    if limit is None : return False 
    last_synced = models.Sync.objects.filter( process = model_class.__name__ ).first()
    if last_synced : 
        if (datetime.datetime.now() - last_synced.time).seconds < limit : return True
    return False 

def check_all_last_sync(limit) :
    SyncTuple = namedtuple("sync_tuple",["sales","adjustment","collection"])
    return SyncTuple( *[ check_last_sync(model,limit) for model in [models.Sales,models.Adjustment,models.Collection]] )

def sync_ikea_report(download_function,insert_function,model_class,kwargs) : 
    last_updated_date = min( model_class.objects.aggregate(date = Max("date"))["date"] or datetime.date(2024,4,1),
                                         datetime.date.today() - datetime.timedelta(days=2) )    
    models.Sync.objects.update_or_create( process = model_class.__name__ , defaults={"time" : datetime.datetime.now()})
    print( "Synced :", model_class.__name__ )
    df = download_function(last_updated_date,datetime.date.today())
    model_class.objects.filter(date__gte = last_updated_date).delete()
    return insert_function(df,**kwargs)

def sync_all_reports(billing = None,limit = None) :
    last_sync = check_all_last_sync(limit)
    if all(last_sync) : return 
    if billing is None : billing = Billing()
    if not last_sync.sales : 
        sync_ikea_report(billing.sales_reg, SalesInsert,models.Sales,{"gst" : None,"permanent" : False})
    if not last_sync.adjustment : 
        sync_ikea_report(billing.crnote, AdjustmentInsert,models.Adjustment,{})
    if not last_sync.collection : 
        sync_ikea_report(billing.collection, CollectionInsert,models.Collection,{})

def update_salesman_collection() : 
    max_time = models.SalesmanCollection.objects.aggregate(time = Max("time"))["time"]
    if max_time : max_time = max_time.astimezone(timezone("UTC"))
    db =  client["test"]["colls"]
    if max_time : rows = db.find({"time" : { "$gt" :  max_time }}) 
    else : rows = db.find() 
    for row in rows : 
        chq_id = str(row["_id"])
        row["time"] = row["time"] + datetime.timedelta(hours=5,minutes=30)
        models.SalesmanCollection.objects.get_or_create(id = chq_id , defaults = {"amt" :row["amount"], "date" :row["date"] , "time" : row["time"] , 
                                                                                    "salesman": row["user"] , "type" : row["type"]})
        for bill in row["bills"] : 
            models.SalesmanCollectionBill.objects.get_or_create(id = str(bill["_id"]) , defaults = 
                                                        {"inum_id" : bill["bill_no"] , "amt" :bill["amount"],  "chq_id" : chq_id})
                    


billing_process_names = ["SYNC" , "PREVBILLS" , "RELEASELOCK" , "COLLECTION", "ORDER"  , "REPORTS" , 
                          "DELIVERY" , "DOWNLOAD" , "PRINT" ][:-2]
billing_lock = threading.Lock()

def run_billing_process(billing_log,params : dict) :
    
    today =datetime.date.today()
    last_billing = models.Billing.objects.filter(start_time__gte = today).order_by("-start_time")
    orders = models.Orders.objects.filter(billing = last_billing[1]) if last_billing.count() > 1 else models.Orders.objects.none()

    line_count = int(params["line_count"][0])    
    # today_pushed_collections = models.PushedCollection.objects.filter( billing__start_time__gte = today ).values_list("party_code",flat=True)
    lines_count = { order.order_no : order.products.count() for order in models.Orders.objects.filter(date = today) }
    delete_orders = [ order.order_no for order in orders.filter(delete = True).all() ]
    creditrelease = list(orders.filter(release = True,delete=False,creditlock=True))
    creditrelease = pd.DataFrame([{ "partyCode":order.party_id , "parCodeRef":order.party_id , "parHllCode": order.party.hul_code , 
                       "showPLG" : order.beat.plg.replace('+','%2B') } for order in creditrelease ])
    if len(creditrelease.index) :
        creditrelease = creditrelease.groupby(["partyCode","parCodeRef","parHllCode","showPLG"]).size().reset_index(name='increase_count')
        creditrelease = creditrelease.to_dict(orient="records")
    else : 
        creditrelease = []
    forced_orders = [ order.order_no for order in orders.filter(force_order = True).all() ]
    
    print( delete_orders )
    print( forced_orders )
    print( creditrelease )
    
    def filter_orders_fn(order: pd.Series) : 
        return all([
             order.on.count() <= line_count,
             (order.on.iloc[0] not in lines_count) or (lines_count[order.on.iloc[0]] == order.on.count()),  
             "WHOLE" not in order.m.iloc[0] ,
             (order.t * order.cq).sum() >= 200
        ]) or (order.on.iloc[0] in forced_orders)

    billing = Billing(filter_orders_fn= filter_orders_fn)
    billing_process_functions = [ billing.Sync , billing.Prevbills ,  (lambda : billing.release_creditlocks(creditrelease)) , 
                                  billing.Collection ,  (lambda : billing.Order(delete_orders)) ,  (lambda : sync_all_reports(billing)) ,  
                                  billing.Delivery , billing.Download , billing.Printbill ]
                            
    billing_process =  dict(zip(billing_process_names,billing_process_functions)) 
    order_objects = None 

    for process_name,process in billing_process.items() : 
        obj = models.ProcessStatus.objects.get(billing=billing_log,process=process_name)
        obj.status = 2
        obj.save()    
        start_time = time.time()
        
        try : 
            process()

            if process_name == "ORDER" : 
 
                orders = billing.all_orders
                
                models.Party.objects.bulk_create([ 
                    models.Party( name = row.p ,code = row.pc ) 
                    for _,row in orders.drop_duplicates(subset="pc").iterrows() ],
                 update_conflicts=True,
                 unique_fields=['code'],
                 update_fields=["name"])
                filtered_orders = billing.filtered_orders.on.values
                
                ## Warning add and condition 
                order_objects:list[models.Orders] = models.Orders.objects.bulk_create([ 
                    models.Orders( order_no=row.on,party_id = row.pc,salesman=row.s, 
                            creditlock = ("Credit Exceeded" in row.ar) , place_order = (row.on in filtered_orders) , 
                        beat_id = row.mi , billing = billing_log , date = datetime.datetime.now().date() , type = row.ot   ) 
                    for _,row in orders.drop_duplicates(subset="on").iterrows() ],
                 update_conflicts=True,
                 unique_fields=['order_no'],
                 update_fields=["billing_id","type","creditlock","place_order"])
                
                prev_allocated_value = { order.order_no :  order.allocated_value() for order in order_objects }
        
                models.OrderProducts.objects.filter(order__in = order_objects,allocated = 0).update(allocated = F("quantity"),reason = "Guessed allocation")
                models.OrderProducts.objects.bulk_create([ models.OrderProducts(
                    order_id=row.on,product=row.bd,batch=row.bc,quantity=row.cq,allocated = row.aq,rate = row.t,reason = row.ar) for _,row in orders.iterrows() ] , 
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

                update_salesman_collection()

            if process_name == "COLLECTION" : 
               
               models.PushedCollection.objects.bulk_create([ models.PushedCollection(
                   billing = billing_log, party_code = pc) for pc in billing.pushed_collection_ids ])
            
            if process_name == "REPORTS" and (order_objects is not None) : 
                for order in order_objects :                     
                    qs = models.Outstanding.objects.filter(party = order.party,beat = order.beat.name,balance__lte = -1)
                    today_bill_count = models.Sales.objects.filter(party = order.party,beat = order.beat.name,
                                                                   date = datetime.date.today()).count()
                    print(order.party.name,today_bill_count,qs.count())
                    if (today_bill_count == 0) and (qs.count() == 1) : 
                        bill_value = order.bill_value()
                        outstanding_bill = qs.first()
                        outstanding_value = -outstanding_bill.balance
                        print(order.party.name , bill_value , outstanding_value)
                        if bill_value < 200 : continue
                        
                        max_outstanding_day =  (today - outstanding_bill.date).days
                        max_collection_day = models.Collection.objects.filter(party = order.party , date = today).aggregate(date = Max("bill__date"))["date"]
                        max_collection_day = (today - max_collection_day).days if max_collection_day else 0   
                        if (max_collection_day > 21) or (max_outstanding_day >= 21): 
                            continue 

                        if (bill_value <= 500) or (outstanding_value <= 500):
                            order.release = True 
                            order.save()
                            print(order.party.name , " release" )
                    
            if process_name == "DELIVERY" and billing.bills : 
                billing_log.start_bill_no = billing.bills[0]
                billing_log.end_bill_no = billing.bills[-1]
                billing_log.bill_count = len(billing.bills)
                billing_log.save()

            obj.status = 1

        except Exception as e :
            traceback.print_exc()
            billing_log.error = str(traceback.format_exc())
            obj.status = 3
        
        end_time = time.time()
        time_taken = end_time - start_time
        obj.time = round(time_taken,2)
        obj.save()

        if obj.status == 3 : 
            billing_log.end_time = datetime.datetime.now() 
            billing_log.status = 3 
            billing_log.save()
            billing_lock.release()
            return 
        
    billing_log.end_time = datetime.datetime.now() 
    billing_log.status = 1 
    billing_log.save()
    billing_lock.release()

def start(request) :
    if not billing_lock.acquire(blocking=False) : 
        return False
    ## Neccesary to create the billing_log before sending response , as the creditlock table depends on the latest billing
    billing_log = models.Billing(start_time = datetime.datetime.now(), status = 2)
    billing_log.save()
    for process_name in billing_process_names :
        models.ProcessStatus(billing = billing_log,process = process_name,status = 0).save()    
    thread = threading.Thread( target = run_billing_process , args = (billing_log,dict(request.POST),) )
    thread.start() 
    return True 

def get_bill_statistics(request) -> list : 

    ## Billing Statistics Admin
    class ProcessStatusAdmin(admin.ModelAdmin):
        actions = None
        ordering = ("id",)
        
        def get_queryset(self, request):
            qs = super().get_queryset(request)
            last_process = qs.last()
            if last_process is None : return qs 
            return qs.filter(billing = last_process.billing)
        
        def colored_status(self,obj):
            class_name = ["unactive","green","blink","red"][obj.status]
            return format_html(f'<span class="{class_name} indicator"></span>')
        colored_status.short_description = ""

        def time(obj):
            return (f"{obj.time} SEC") if obj.time is not None else '-'
        
        list_display = ["colored_status","process",time]
        
    class LastBillStatisticsAdmin(admin.ModelAdmin):
        actions = None
        list_display = ["type","count"]
        def get_queryset(self, request) :
            return models.BillStatistics.objects.filter( type__contains = "LAST" ).reverse()
    
    class TodayBillStatisticsAdmin(admin.ModelAdmin):
        actions = None
        list_display = ["type","count"]
        def get_queryset(self, request) :
            return models.BillStatistics.objects.exclude( type__contains = "LAST" ).reverse()

    today = datetime.date.today()
    sales_qs = models.Sales.objects.filter(date  = today,type = "sales")
    today_stats = {"bill_count" : sales_qs.exclude(beat__contains = "WHOLE").count() , 
                   "collection_count" : models.Collection.objects.filter(date  = today).count() }

    if today_stats["bill_count"] : 
       today_stats |= {"bills_start" : sales_qs.first().inum , "bills_end" : sales_qs.last().inum }
    else :
       today_stats |= {"bills_start" : None , "bills_end" : None }

    today_stats |= models.Billing.objects.filter(start_time__gte = today).aggregate( 
        success = Count("status",filter=Q(status = 1)) , failed = Count("status",filter=Q(status = 3))
    )

    last_stats = models.Billing.objects.filter(start_time__gte = today).order_by("-start_time").first()

    if last_stats is not None : 
        stats = {"LAST BILLS COUNT" : last_stats.bill_count or 0,"LAST COLLECTION COUNT" : last_stats.collection.count() ,  
                    "LAST BILLS" : f'{last_stats.start_bill_no or ""} - {last_stats.end_bill_no or ""}', 
                    "LAST STATUS" : ["DID NOT START","SUCCESS","ONGOING","ERROR"][last_stats.status] , 
                    "LAST TIME" : f'{last_stats.start_time.strftime("%H:%M:%S")}' }
    else : 
        stats = {"LAST BILLS COUNT" : 0 ,"LAST COLLECTION COUNT" : 0 , "LAST BILLS" : "-",  "LAST STATUS" : "-" }
    
    stats |= { "TODAY BILLS COUNT" : today_stats["bill_count"] , "TODAY COLLECTION COUNT" : today_stats["collection_count"] , 
    "TODAY BILLS" : f'{today_stats["bills_start"]} - {today_stats["bills_end"]}'  ,"SUCCESSFULL" : today_stats["success"] , 
    "FAILURES" : today_stats["failed"] }
    
    models.BillStatistics.objects.all().delete()
    models.BillStatistics.objects.bulk_create([ models.BillStatistics(type = k,count = str(v)) for k,v in stats.items() ])

    tables = [0,0,0] 
    tables[0] = LastBillStatisticsAdmin(models.BillStatistics,admin_site).get_changelist_instance(request)
    tables[0].formset = None
    tables[1] = ProcessStatusAdmin(models.ProcessStatus,admin_site).get_changelist_instance(request)
    tables[1].formset = None   
    tables[2] = TodayBillStatisticsAdmin(models.BillStatistics,admin_site).get_changelist_instance(request)
    tables[2].formset = None
    return tables 

def get_last_billing() : 
    billing_qs = models.Billing.objects.all().order_by("-start_time")
    last_billing = billing_qs.first()      
    if last_billing : 
        order_status = models.ProcessStatus.objects.filter(billing = last_billing,process = "ORDER").first()
        if order_status and (order_status.status in [1,3]) :  pass
        else : 
            if billing_qs.count() > 1 : 
                last_billing = billing_qs[1]
    return last_billing

class ChangeOnlyAdminModel(admin.ModelAdmin) : 
    def has_add_permission(self, request,obj = None):
        return False
    def has_change_permission(self, request, obj=None):
        return True
    def has_delete_permission(self, request, obj=None):
        return False
   
class ReadOnlyModel() : 
    def has_add_permission(self, request,obj = None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class OrderProductsInline(ReadOnlyModel,admin.TabularInline) : 
    model = models.OrderProducts
    show_change_link = True
    verbose_name_plural = "products"

class BaseOrderAdmin(ChangeOnlyAdminModel) :   
    inlines = [OrderProductsInline]
    readonly_fields = ("order_no",'date','party','type','salesman','beat',"billing",'release','creditlock','delete','place_order','force_order')
    actions = None

    def value(self,obj) : 
        return obj.bill_value()
    
    def OS(self,obj) :
        today = datetime.date.today() 
        bills = [  f"{-round(bill.balance)}*{(today - bill.date).days}"
                 for bill in models.Outstanding.objects.filter(party = obj.party,beat = obj.beat.name,balance__lte = -1).all() ]
        return "/ ".join(bills)
    
    def coll(self,obj) : 
        today = datetime.date.today() 
        coll = [  f"{round(coll.amt)}*{(today - coll.bill.date).days}"
                 for coll in models.Collection.objects.filter(party = obj.party , date = today).all() ]
        return "/ ".join(coll)
    
    def phone(self,obj) : 
        phone = obj.party.phone or "-"
        return format_html('<a href="tel:+91{}" target="_blank">{}</a>',phone,phone)

    def lines(self,obj) : 
        return len([ product for product in obj.products.all() if product.allocated != product.quantity])
    

## Billing Admin
class BillingAdmin(BaseOrderAdmin) :   

    change_list_template = "billing.html"
    list_display_links = ["party"]
    list_display = ["release","party","lines","value","OS","coll","salesman","beat","phone","delete","cheque"] 
    list_editable = ["release","delete"]
    ordering = ["-release","salesman"]

    def cheque(self,obj) : 
        qs = models.SalesmanCollection.objects.filter(time__gte = datetime.date.today()).filter(bills__inum__party = obj.party)
        colls = qs.all()
        if len(colls) : 
            ids = ",".join([ coll.id for coll in colls ])
            value = sum([ coll.amt for coll in colls ])
            return format_html("<a href='/app/salesmancollection/?id__in={}' target='_blank'>{}</a>",ids,value) 
        else : 
            return ""
        
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if (not hasattr(request,"filter_queryset")) or  (not request.filter_queryset) : return qs 
        qs = qs.filter(creditlock=True) 
        billing_qs = models.Billing.objects.all().order_by("-start_time")
        last_billing = billing_qs.first()      
        # billings = list(models.Billing.objects.filter(start_time__gte = datetime.datetime.now() - datetime.timedelta(minutes=30)))
        if last_billing : 
            order_status = models.ProcessStatus.objects.filter(billing = last_billing,process = "ORDER").first()
            if order_status and (order_status.status in [1,3]) :  pass
            else : 
                if billing_qs.count() > 1 : 
                    last_billing = billing_qs[1]
        if last_billing is None : return qs.none() 
        return qs.filter(billing = last_billing,place_order=True) #WARNING
    
    def changelist_view(self, request, extra_context=None):   
        ## This attribute says get_queryset function whether to filter the creditlocks only for last billing (or) all billing
        request.filter_queryset = False 
        today = datetime.date.today()
        time_interval = int( request.POST.get("time_interval",10) )
        time_interval_milliseconds = time_interval * 1000 * 60
        next_action = "unknown"

        if request.method == "POST" :             
            action = request.POST.get("action_name")

            if (action == "start") or (action == "quit"): 
                original_post = request.POST.copy()
                edited_post = request.POST.copy()
                edited_post["_save"] = "Save"
                request._set_post(edited_post)
                super().changelist_view( request )
                request._set_post(original_post)

            if action == "start" : 
                start(request)
                next_action = "refresh"
            if action == "refresh" :
                next_action = "refresh" if billing_lock.locked() else "start"
            if action == "quit" : 
                time_interval_milliseconds = int(1e7)
            if next_action == "refresh" :
                time_interval_milliseconds = 5 * 1000
            
            print("action :",action,"next :",next_action,"time :",time_interval_milliseconds)

        tables = get_bill_statistics(request) 
        line_count = int(request.POST.get("line_count",100))
        request.filter_queryset = True 

        return super().changelist_view( request, extra_context={ "title" : "" ,"tables" : tables ,  
        "time_interval_milliseconds" : time_interval_milliseconds , "time_interval" : time_interval , 
        "line_count" : line_count , "auto_action_type" : next_action  })

class OrdersAdmin(BaseOrderAdmin) :
   
    list_display_links = None
    list_display =  ["partial","order","party","lines","value","OS","coll","salesman","beat","creditlock","delete","phone"] #"release","place_order", 
    ordering = ["place_order"]
    actions = ["force_order","delete_orders"]

    def lines(self, obj):
        return format_html("<span style='font-weight:500 !important; font-size : 14px !important'> {} </span>",super().lines(obj))
    
    def value(self, obj):
        return format_html("<span style='font-weight:500 !important;font-size : 14px !important'> {} </span>",super().value(obj))
    
    class CustomFilter(admin.SimpleListFilter):
        title = 'filter'
        parameter_name = 'filter'

        def lookups(self, request, model_admin):
            return (
                ('less_than_200', 'less_than_200'),
                ('less_than_10_lines', 'less_than_10_lines'),
                ('already_billed', 'already_billed'),
            )

        def queryset(self, request, queryset):
            today =datetime.date.today()
            if self.value() == 'less_than_200':
                return queryset.annotate(bill_value_field = Sum(F('products__quantity') * F('products__rate'))).filter(
                        bill_value_field__lt = 200).order_by("bill_value_field")
            if self.value() == 'less_than_10_lines':
                return queryset.annotate(lines_count = Count(F('products'))).filter(
                        lines_count__lt = 10)
            if self.value() == 'already_billed':
                return queryset.filter(order_no__in = [ order.order_no for order in queryset if order.partial() ])
            return queryset

    class LastFilter(admin.SimpleListFilter):
        title = 'Billing'
        parameter_name = 'billing'

        def lookups(self, request, model_admin):
            return (('last','last'),)

        def queryset(self, request, queryset):
            value = self.value()
            if value == 'last':
                last_billing = get_last_billing()
                if last_billing is None : queryset.none()
                return queryset.filter(billing = last_billing)
            return queryset

    list_filter = [CustomFilter,LastFilter]

    def partial(self,obj) :
        return obj.partial()
    partial.boolean = True  

    def order(self, obj):
        url = f'/app/ordersproxy/{obj.order_no}/change/' 
        return format_html('<a href="{}" target="_blank">{}</a>',url,obj.order_no)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if "/change" in request.path : return qs 
        qs = qs.exclude(beat__name__contains = "WHOLE")
        return qs.exclude(products__allocated = F("products__quantity")).distinct()
    
    def changelist_view(self, request, extra_context=None):   
        title_prefix = "Pending Values" if "place_order__exact=1" in request.get_full_path() else "Rejected Orders" 
        title = f"{title_prefix} @ {get_last_billing().start_time.strftime('%d %B %Y, %I:%M:%S %p')}"
        return super().changelist_view( request, extra_context={ "title" : title })

    @admin.action(description="Force Place Order & Release Lock")
    def force_order(self, request, queryset) : 
        queryset.update(place_order = True,force_order=True)
        queryset.filter(creditlock=True).update(release = True)
    
    @admin.action(description="Delete Orders")
    def delete_orders(self, request, queryset) : 
        queryset.update(delete = True)


class BankStatementUploadForm(forms.Form):
    excel_file = forms.FileField()

class BankCollectionForm(forms.ModelForm):
    party  = forms.CharField(label="Party",required=False,disabled=True)
    balance  = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label='Outstanding',disabled=True)
    class Meta:
        model = models.BankCollection
        fields = ["bill","party","balance","amt"]
        widgets = {
             'bill': dal.autocomplete.ModelSelect2(url='billautocomplete') ,  
             "amt" : forms.TextInput()   ,
        }

class BankCollectionInline(admin.TabularInline) : 
    model = models.BankCollection
    show_change_link = False
    verbose_name_plural = "collection"
    form = BankCollectionForm
    extra = 1 
    class Media:
        js = ('admin/js/bank_inline.js',)

class BankAdmin(ChangeOnlyAdminModel) : 

    change_list_template = "bank.html"
    list_display = ["date","ref","desc","amt","saved","pushed"]
    actions = ["push_collection","push_collection_static"]
    readonly_fields = ["date","pushed","ref","desc","amt","bank","idx","id"]
    inlines = [BankCollectionInline]
    list_display_links = ["date","ref","desc","amt","pushed"] 
    list_filter = ["pushed","date"]
    search_fields = ["amt","desc"]

    def saved(self,obj) : 
        return bool(obj.collection.count() > 0)  
    saved.boolean = True  
    
    @admin.action(description="Save without Push")
    def push_collection_static(self, request, queryset) : 
        queryset.update(pushed = True)

    @admin.action(description="Push Collection")
    def push_collection(self, request, queryset):
        queryset = queryset.filter(pushed = False)
        if not ('apply' in request.POST) :
            chqs = list(queryset)
            colls = [ coll for chq in chqs for coll in chq.collection.all() ]
            if len(colls) == 0 : 
                messages.warning(request,"No collections present for the selected cheques")
                return redirect(request.path)
            value = sum([ coll.amt for coll in colls ])
            return render(request, 'admin/push_collection_confirmation.html', context={'items': queryset,
                                                                            "total_chqs":len(chqs),"total_bills" : len(colls) , "amt" : value , 
                                                                            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME })
        billing = Billing(None,None,None,None,None)
        coll = billing.donwload_manual_collection()
        manual_coll = []
        bill_chq_pairs = []
        for bank_obj in queryset.all() : 
            for coll_obj in bank_obj.collection.all() :
                bill_no  = coll_obj.bill_id 
                row = coll[coll["Bill No"] == bill_no].copy()
                row["Mode"] = ( "Cheque/DD"	if bank_obj.type == "cheque" else "Cheque/DD") ##Warning
                row["Retailer Bank Name"] = "KVB 650"	
                row["Chq/DD Date"]  = bank_obj.date.strftime("%d/%m/%Y")
                row["Chq/DD No"] = chq_no = f"{bank_obj.date.strftime('%d%m')}{bank_obj.idx}".lstrip('0')
                row["Amount"] = coll_obj.amt
                manual_coll.append(row)
                bill_chq_pairs.append((chq_no,bill_no))

        manual_coll = pd.concat(manual_coll)
        manual_coll["Collection Date"] = datetime.date.today()
        print("manual collection :",manual_coll)

        f = BytesIO()
        manual_coll.to_excel(f,index=False)
        f.seek(0)
        res = billing.upload_manual_collection(f)

        print("upload collection :",pd.read_excel(billing.download_file(res["ul"])).iloc[0] )

        settle_coll = billing.download_settle_cheque()
        settle_coll = settle_coll[ settle_coll.apply(lambda row : (str(row["CHEQUE NO"]),row["BILL NO"]) in bill_chq_pairs ,axis=1)].iloc[:1]
        settle_coll["STATUS"] = "SETTLED"
        f = BytesIO()
        settle_coll.to_excel(f,index=False)
        f.seek(0)
        res = billing.upload_settle_cheque(f)
        print("response collection :",pd.read_excel(billing.download_file(res["ul"])) )
        queryset.update(pushed = True)
        sync_ikea_report(billing.collection, CollectionInsert,models.Collection,{})

    def changelist_view(self, request, extra_context=None):

        if request.method == 'GET' :
            if not check_last_sync(models.Sales,60*60) : 
               billing = Billing()
               sync_ikea_report(billing.sales_reg, SalesInsert,models.Sales,{"gst" : None,"permanent" : False})
               sync_ikea_report(billing.crnote, AdjustmentInsert,models.Adjustment,{})
            if not check_last_sync(models.Collection,60*10) : 
               sync_ikea_report(Billing().collection, CollectionInsert,models.Collection,{})

        form = BankStatementUploadForm()

        if request.method == 'POST' and 'excel_file' in request.FILES:
            form = BankStatementUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['excel_file']
                df = pd.read_excel(excel_file).rename(columns={"Txn Date":"date","Credit":"amt","Ref No./Cheque No.":"ref","Description":"desc"})
                df["date"] = pd.to_datetime(df["date"])
                df["idx"] = df.groupby("date").cumcount() + 1 
                df = df[["date","ref","desc","amt","idx"]]
                df["id"] = df["date"].dt.strftime("%d%m%Y") + df['idx'].astype(str)
                df["date"] = df["date"].dt.date
                df.amt = df.amt.astype(str).str.replace(",","").apply(lambda x  : float(x.strip()) if x.strip() else 0)
                df["bank"] = "sbi"
                bulk_raw_insert("bank",df,upsert=True)
                messages.success(request, "Statement successfully uploaded")
            else : 
                messages.error(request, "Statement upload failed")
            return redirect(request.path)

        extra_context = extra_context or {}
        extra_context['form'] = form
        
        return super().changelist_view(request, extra_context=extra_context | {"title" : ""})

    def save_model(self, request, obj, form, change):
        obj._save_deferred = True  # Flag to save it later in save_related()

    def has_change_permission(self, request, obj=None):
        return not (obj and (obj.pushed))
        
    def save_related(self, request, form, formsets, change):
        bank_obj = form.instance 
        total_amt = 0 
        for formset in formsets:
            if formset.model == models.BankCollection :
                for inline_form in formset.forms:
                    obj = inline_form.instance
                    is_deleted = inline_form.cleaned_data.get('DELETE')
                    if obj.amt and (not is_deleted):
                        total_amt += obj.amt    

        if abs(total_amt - bank_obj.amt) > 5 :  
            messages.error(request,f"Cheque Value & Collection Value Mismatch \n Total value : {total_amt} , Cheque amt : {bank_obj.amt}")
            formsets.clear()
        else : 
            if hasattr(form.instance, '_save_deferred') and form.instance._save_deferred:
              super().save_model(request,bank_obj,form,change)    
        super().save_related(request,form,formsets, change)
    
class OutstandingAdmin(ReadOnlyModel,admin.ModelAdmin) : 
    change_list_template = "outstanding.html"
    list_display = ["inum","party","beat","balance","phone","days"]
    today = datetime.date.today()
    ordering = ["date"]
    
    
    class DaysAgoListFilter(admin.SimpleListFilter):
        title = 'Outstanding Days'
        parameter_name = 'date_before_today'

        def lookups(self, request, model_admin):
            return (
                ('14_days', '>= 14 days'),
                ('21_days', '>= 21 days'),
                ('28_days', '>= 28 days'),
                ('30_days', '>= 30 days'),
            )

        def queryset(self, request, queryset):
            today =datetime.date.today()
            if self.value() == '14_days':
                return queryset.filter(date=today - datetime.timedelta(days=14))
            elif self.value() == '21_days':
                return queryset.filter(date=today - datetime.timedelta(days=21))
            elif self.value() == '28_days':
                return queryset.filter(date=today - datetime.timedelta(days=28))
            elif self.value() == '30_days':
                return queryset.filter(date=today - datetime.timedelta(days=30))
            return queryset

    list_filter = [DaysAgoListFilter]
    
    def phone(self,obj) : 
        return obj.party.phone
    
    def days(self,obj) : 
        return (self.today - obj.date).days
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).filter(balance__lte = -1)
    
    def changelist_view(self, request, extra_context=None):
        # if all(check_all_last_sync(limit= 5*60)) :     
        sync_all_reports(limit = 5*60)
        return super().changelist_view(request, (extra_context or {})| {"title" : "Outstanding Report"})


class SalesCollectionBillInline(ReadOnlyModel,admin.TabularInline) : 
    model = models.SalesmanCollectionBill
    verbose_name_plural = "bills"
    list_display = ["inum","amt"]
 
class SalesCollectionAdmin(ReadOnlyModel,admin.ModelAdmin) :

    list_display = ["party","cheque_date","amt","salesman","time"]
    list_filter = ["time","salesman"]
    ordering = ["salesman"]
    inlines = [SalesCollectionBillInline]
    
    def party(self,obj) : 
        bill = obj.bills.first()
        return bill.inum.party.name if bill else "-"
    
    def cheque_date(self,obj) : 
        return obj.date 
    
    def has_delete_permission(self, request, obj=None):
        return True
   
    def get_changelist(self, request: HttpRequest, **kwargs: Any) -> Type[ChangeList]:
        update_salesman_collection()
        return super().get_changelist(request, **kwargs)

class PrintAdmin(ChangeOnlyAdminModel) :
    list_display = ["bill","party","salesman","type","time"]
    ordering = ["bill"]
    actions = ["both_copy","loading_sheet_salesman","first_copy","second_copy","loading_sheet"]

    def salesman(self,obj) :
        return models.Beat.objects.filter(name = obj.bill.beat).first().salesman_name

    def group_consecutive_bills(self,bills):

        def extract_serial(bill_number):
            match = re.search(r'(\D+)(\d{5})$', bill_number)
            if match:
                return match.group(1), int(match.group(2))  # Return prefix and serial number as a tuple
            return None, None

        sorted_bills = sorted(bills, key=lambda x: extract_serial(x))

        groups = []
        current_group = []
        prev_prefix, prev_serial = None, None

        for bill in sorted_bills:
            prefix, serial = extract_serial(bill)
            if not prefix:
                continue

            if prev_prefix == prefix and prev_serial is not None and serial == prev_serial + 1:
                current_group.append(bill)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [bill]

            prev_prefix, prev_serial = prefix, serial

        if current_group:
            groups.append(current_group)

        return groups

    def print_bills(self,request,billing: Billing,queryset,type) : 
        groups = self.group_consecutive_bills([ bill.bill_id for bill in queryset ])
        for group in groups : 
            billing.bills = group 
            if type == "first_copy" : billing.Download(pdf = True,txt = False)
            if type == "second_copy" : billing.Download(pdf = False,txt = True)
            if type == "loading_sheet" :
                loading_sheet.create_pdf(billing.loading_sheet(group) , header = False)
            if type == "loading_sheet_salesman" :
                beats =  list(queryset.values_list("bill__beat",flat=True))
                salesmans = list(models.Beat.objects.filter(name__in = beats).values_list("salesman_name",flat=True).distinct())
                salesman =  salesmans[0] if len(salesmans) == 1 else ""
                loading_sheet.create_pdf(billing.loading_sheet(group) , header = True,salesman=salesman)
                

            fname_map = {"first_copy" : "bill.pdf","second_copy" : "bill.docx",
                           "loading_sheet_salesman":"loading.pdf","loading_sheet":"loading.pdf"}
            status = billing.Printbill(print_files = [ fname_map[type] , ])
            status = True  #warning:

            if status : 
                if type == "first_copy" : queryset.update(type = "first_copy", time = datetime.datetime.now()) 
                if type == "loading_sheet_salesman" : queryset.update(type = "loading_sheet", time = datetime.datetime.now()) 

            if status :
                messages.success(request,f"Succesfully printed {type.upper()} : {group[0]} - {group[-1]}")
            else : 
                messages.error(request,f"Bills failed to print {type.upper()} : {group[0]} - {group[-1]}")

    def base_print_action(self, request, qs , type ) :
        i = Billing()
        type = defaultdict(lambda : False,type)
        for print_type,is_true in type.items() : 
            if is_true : 
                if print_type in ["first_copy","loading_sheet_salesman"] : 
                   if qs.filter(time__isnull = False).count() : 
                       messages.warning(request,f"Bills are already printed for {print_type.upper()}")

                   self.print_bills(request, i , qs.filter(time__isnull = True) , type = print_type)
                else : 
                   self.print_bills(request, i , qs , type = print_type)
                 
    @admin.action(description="Both Copy")
    def both_copy(self,request,queryset) : 
        self.base_print_action(request,queryset,{"first_copy" : True,"second_copy" : True})
    
    @admin.action(description="First Copy")
    def first_copy(self,request,queryset) : 
        self.base_print_action(request,queryset,{"first_copy" : True})

    @admin.action(description="Second Copy")
    def second_copy(self,request,queryset) : 
        self.base_print_action(request,queryset,{"second_copy" : True})

    @admin.action(description="Salesman Loading Sheet")
    def loading_sheet_salesman(self,request,queryset) : 
        self.base_print_action(request,queryset,{"loading_sheet_salesman" : True})

    @admin.action(description="Plain Loading Sheet")
    def loading_sheet(self,request,queryset) : 
        self.base_print_action(request,queryset,{"loading_sheet" : True})

    def party(self,obj) : 
        return obj.bill.party.name
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).filter(bill__date = datetime.date.today())

# class SalesAdmin(ReadOnlyModel,admin.ModelAdmin) : 
#     list_display = ["inum","party","beat","amt","date","OS","days"]
#     ordering = ["date"]

#     def OS(self,obj) : 
#         bills = list(models.OutstandingRaw.objects.filter(party_id = obj.party_id,beat = obj.beat,date__lt = obj.date).values_list("inum",flat=True))
#         bills = models.OutstandingRaw.objects.filter(inum__in = bills,date__lte = obj.date).values('inum').annotate(bal = -Sum("amt"),
#                         date = (obj.date - Min("date"))).exclude(bal__lt = 1)
        
#         return "/".join([ f'{bill["bal"]}*{bill["date"].days}' for bill in bills ])

#     def days(self,obj) : 
#         return (models.OutstandingRaw.objects.filter(inum = obj.inum).aggregate(date = Max("date"))["date"] - obj.date).days
    
#     def coll(self,obj) : 
#         bills = list(models.OutstandingRaw.objects.filter(party_id = obj.party_id,beat = obj.beat,date__lt = obj.date).values_list("inum",flat=True))
#         coll = models.OutstandingRaw.objects.filter(inum__in = bills,date = obj.date).values('inum').annotate(bal = Sum("amt"))
#         return "/".join([ f'{bill["bal"]}' for bill in coll ])

#     def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
#         party = "SRI MANONMANI STORE" #"Saravana Pazhamudir Cholai-F" #"SRI BALAJI SUPER MARKET-D" #"A V STORE-D"
#         return super().get_queryset(request).filter(party_id = "P16048")

admin_site.register(models.Outstanding,OutstandingAdmin)
admin_site.register(models.Orders,BillingAdmin)
admin_site.register(models.OrdersProxy,OrdersAdmin)
admin_site.register(models.Bank,BankAdmin)
admin_site.register(models.SalesmanCollection,SalesCollectionAdmin)
admin_site.register(models.Print,PrintAdmin)
# admin_site.register(models.Sales,SalesAdmin)


