# your_app/middleware.py

import datetime
from django.contrib.admin.views.main import ChangeList
from django.utils.deprecation import MiddlewareMixin
from app.common import bulk_raw_insert, query_db
import app.models as models 
from custom.classes import Billing
from app.sales_import import PartyInsert,CollectionInsert

verified_today_sync = False 

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
            beats = i.get_plg_maps()
            bulk_raw_insert("beat",beats)
        if last_synced["Party"] < today : 
            PartyInsert(i.party_master())
        if last_synced["Collection"] < today : 
           fromd = today - datetime.timedelta(days = 15)
           coll_report = i.collection(fromd,today)
           models.Collection.objects.filter(date__gte = fromd).delete()
           CollectionInsert(coll_report)

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
        