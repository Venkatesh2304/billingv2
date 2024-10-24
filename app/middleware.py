# your_app/middleware.py

import datetime
from django.contrib.admin.views.main import ChangeList
from django.utils.deprecation import MiddlewareMixin
import pandas as pd
from app.admin import sync_reports
from app.common import bulk_raw_insert, query_db
import app.models as models 
from custom.classes import Billing
from app.sales_import import AdjustmentInsert, PartyInsert,CollectionInsert, SalesInsert
from custom.Session import client
from django.db import connection 

verified_today_sync = False 

def sync_beat_parties_ikea(force = False) :

    today = datetime.date.today() if not force else (datetime.date.today() + datetime.timedelta(days=1))
    newly_synced = sync_reports(limits={"sales":today,"adjustment":today,"collection" : today,"beat": today,"party" : today,"beat" : today} , 
                                min_days_to_sync={"collection":15})
    if newly_synced : 
        models.Outstanding.upload_today_outstanding_mongo()
           
class AdminProcessingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "force-sync" in request.path : 
            sync_beat_parties_ikea(force=True)
            return 
        global verified_today_sync
        if verified_today_sync : return
        urls = ["outstanding","orders","bank"]
        for url in urls : 
            if url in request.path : 
               sync_beat_parties_ikea()
               verified_today_sync = True  
        