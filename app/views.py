# views.py
import datetime
from io import BytesIO
from dal import autocomplete
from django.http import HttpResponse, JsonResponse
import pandas as pd

from app.common import query_db
from .models import Outstanding
from django.db.models import F
from django.db.models.functions import Abs
from django.db.models import Q

def get_outstanding(request, inum):
    try:
        obj = Outstanding.objects.get(inum=inum.split("-")[0])
        return JsonResponse({'balance': str(round(-obj.balance,2)) , 'party' : obj.party.name })
    except Outstanding.DoesNotExist:
        return JsonResponse({'balance': 0,'party': '-'})
    
def get_outstanding_report(request) : 
    date = request.POST.get("date") or str(datetime.date.today()) 
    day = datetime.datetime.strptime(date,"%Y-%m-%d").strftime("%A").lower()
    outstanding = query_db(f"""select salesman_name as salesman , (select name from app_party where party_id = code) as party , beat , inum as bill , 
    (select -amt from app_sales where inum = app_outstanding.inum) as bill_amt , -balance as balance , 
    (select phone from app_party where code = party_id) as phone , 
    round(julianday('{date}') - julianday(date)) as days 
    from app_outstanding left outer join app_beat on app_outstanding.beat = app_beat.name
    where days  like '%{day}%' and balance <= -1 and beat not like '%WHOLESALE%' """,is_select = True)
    pivot_fn = lambda df : pd.pivot_table(df,index=["salesman","beat","party","bill"],values=['balance',"days","phone"],aggfunc = "first")
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    pivot_fn(outstanding[outstanding.days >= 21]).to_excel(writer, sheet_name='21 Days')
    pivot_fn(outstanding[outstanding.days >= 28]).to_excel(writer, sheet_name='28 Days')
    outstanding.to_excel(writer, sheet_name='ALL BILLS',index=False)
    writer.save()
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="' + f"outstanding_{date}.xlsx" + '"'
    return response 

class BillAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Outstanding.objects.all() #filter(balance__lte = -1)
        if self.q:
            qs = qs.filter(Q(inum__icontains=self.q) | Q(party__name__icontains=self.q)) 
        return qs
