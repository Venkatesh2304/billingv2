# views.py
import datetime
from io import BytesIO
from dal import autocomplete
from django.http import HttpResponse, JsonResponse
import pandas as pd

from app.common import query_db
from custom.classes import Billing
from .models import Outstanding
from django.db.models import F
from django.db.models.functions import Abs
from django.db.models import Q
from django import forms
from django.middleware.csrf import get_token

def get_outstanding(request, inum):
    try:
        obj = Outstanding.objects.get(inum=inum.split("-")[0])
        return JsonResponse({'balance': str(round(-obj.balance,2)) , 'party' : obj.party.name })
    except Outstanding.DoesNotExist:
        return JsonResponse({'balance': 0,'party': '-'})
    
def get_outstanding_report(request) : 
    date = request.POST.get("date") or str(datetime.date.today()) 
    day = datetime.datetime.strptime(date,"%Y-%m-%d").strftime("%A").lower()
    outstanding = query_db(f"""select * from (
    select salesman_name as salesman , (select name from app_party where party_id = code) as party , beat , inum as bill , 
    (select -amt from app_sales where inum = app_outstanding.inum) as bill_amt , -balance as balance , 
    (select phone from app_party where code = party_id) as phone , 
    round(julianday('{date}') - julianday(date)) as days , 
    days as weekday 
    from app_outstanding left outer join app_beat on app_outstanding.beat = app_beat.name
    where  balance <= -1 and beat not like '%WHOLESALE%' )
    where days >= 28 or weekday like '%{day}%'
    """,is_select = True)
    pivot_fn = lambda df : pd.pivot_table(df,index=["salesman","beat","party","bill"],values=['balance',"days","phone"],aggfunc = "first")
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    pivot_fn(outstanding[ (outstanding.days >= 21) & outstanding.weekday.str.contains(day) ]).to_excel(writer, sheet_name='21 Days')
    pivot_fn(outstanding[outstanding.days >= 28]).to_excel(writer, sheet_name='28 Days')
    outstanding.to_excel(writer, sheet_name='ALL BILLS',index=False)
    writer.close()
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="' + f"outstanding_{date}.xlsx" + '"'
    return response 


class ManualPrintForm(forms.Form):
    from_bill = forms.CharField(label='From Bill', max_length=100)
    to_bill = forms.CharField(label='To Bill', max_length=100)

def manual_print_view(request):
    form = ManualPrintForm()
    
    if request.method == 'POST':
        form = ManualPrintForm(request.POST)
        if form.is_valid():
            from_bill = form.cleaned_data['from_bill']
            to_bill = form.cleaned_data['to_bill']
            i = Billing()
            i.bills = [from_bill,to_bill]
            i.Download()

    csrf_token = get_token(request)
    response_html = f"""<form method="post">
             <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
             {form.as_p()}
            <button type="submit">Submit</button>
        </form>"""
    
    return HttpResponse(response_html)

class BillAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Outstanding.objects.all() #filter(balance__lte = -1)
        if self.q:
            qs = qs.filter(Q(inum__icontains=self.q) | Q(party__name__icontains=self.q)) 
        return qs
