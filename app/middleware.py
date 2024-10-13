# your_app/middleware.py

import datetime
from django.contrib.admin.views.main import ChangeList
from django.utils.deprecation import MiddlewareMixin
import pandas as pd
from app.admin import sync_ikea_report
from app.common import bulk_raw_insert, query_db
import app.models as models 
from custom.classes import Billing
from app.sales_import import AdjustmentInsert, PartyInsert,CollectionInsert, SalesInsert
from custom.Session import client
from django.db import connection 

verified_today_sync = False 

def outstanding_mongo_upload() : 
    print("Start Uploading outstanding to mongo DB")
    date = str(datetime.date.today()) 
    day = datetime.datetime.strptime(date,"%Y-%m-%d").strftime("%A").lower()
    db = client["test"]["outstandings"] 
    outstanding = pd.read_sql(f"""select salesman_name as user , (select name from app_party where party_id = code) as party , inum as bill_no , -balance as amount  
        from app_outstanding left outer join app_beat on app_outstanding.beat = app_beat.name
        where  balance <= -1 and days like '%{day}%' """,connection)
    db.delete_many({})
    if len(outstanding.index) :  db.insert_many(outstanding.to_dict('records'))

    db = client["test"]["users"] 
    users = pd.read_sql(f"""select salesman_name as user , 'devaki' as password from app_beat """,connection)
    users = users.drop_duplicates(subset="user")
    for index, row in users.iterrows():
        user ,  password = row['user'] , row['password']
        db.update_one(
            {'user': user},  # Search by the 'user' field
            {'$setOnInsert': {'user': user, 'password': password}},  # Set only if the user doesn't exist
            upsert=True  # If user does not exist, insert the document
        )
    print("Uploaded outstanding to mongo DB")

def get_last_sync(model_class) : 
    last_sync = models.Sync.objects.filter( process = model_class.__name__ ).first() 
    if last_sync : return last_sync.time.date() 
    return datetime.date(2024,4,1)

def sync_beat_parties_ikea(force = False) :
    sync_models = [models.Party,models.Beat,models.Collection]
    last_synced = { model_class.__name__ : get_last_sync(model_class) for model_class in sync_models }
    today = datetime.date.today() if not force else (datetime.date.today() + datetime.timedelta(days=1))
    
    if min(last_synced.values()) < today : 
        
        i = Billing()
        if last_synced["Beat"] < today : 
            query_db("delete from app_beat")
            beats = i.get_plg_maps()
            bulk_raw_insert("beat",beats)

        if last_synced["Party"] < today : 
            PartyInsert(i.party_master())
        
        sync_ikea_report(i.sales_reg, SalesInsert,models.Sales,{"gst" : None,"permanent" : False})
        sync_ikea_report(i.crnote, AdjustmentInsert,models.Adjustment,{})
        
        if last_synced["Collection"] < today : 
           fromd = today - datetime.timedelta(days = 15)
           coll_report = i.collection(fromd,today)
           models.Collection.objects.filter(date__gte = fromd).delete()
           CollectionInsert(coll_report)

        outstanding_mongo_upload()
           
        for model_class in sync_models : 
            models.Sync.objects.update_or_create( 
                process = model_class.__name__ , defaults={"time" : datetime.datetime.now()})

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
        