# views.py
import datetime
from io import BytesIO
import json
import os
import time
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
import pandas as pd

from app.admin import reload_server, sync_reports
from app.common import query_db
from custom.classes import Billing
from .models import Outstanding
from django.db.models import F
from django.db.models.functions import Abs
from django.db.models import Q
from django import forms
from django.middleware.csrf import get_token
from openpyxl import load_workbook

from app import models
from django.utils.safestring import mark_safe
from django.views import View
from django.db.models import Count

def basepack(request) :
    ikea = Billing()
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    stock = ikea.current_stock(today)
    stock = stock[stock.Location == "MAIN GODOWN"]
    stock_original = stock.copy()
    stock = set(stock["Basepack Code"].dropna().astype(int))
    basepack_io = ikea.basepack()         
    wb = load_workbook(basepack_io , data_only = True)
    sh = wb['Basepack Information']
    rows = sh.values
    basepack = pd.DataFrame( columns=next(rows) , data = rows )
    basepack_original = basepack.copy()
    color_in_hex = [cell.fill.start_color.index for cell in sh['A:A']]
    basepack["color"] = pd.Series( color_in_hex[1:])
    basepack = basepack[ basepack["color"] != 52 ][basepack["BasePack Code"].notna()]
    basepack["new_status"] = basepack["BasePack Code"].astype(int).isin(stock)

    
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
    stock_original.to_excel(writer,index=False,sheet_name="currentstock")
    writer.close()
    output.seek(0)

    with open('basepack.xlsx', 'wb+') as f:  
        f.write(output.read())

    print( "Basepack Changed (NEW STATUS COUNTS) : " ,  basepack["Status"].value_counts().to_dict() )
    
    if len(basepack.index) : 
       files = { "file" : ("basepack.xlsx", output ,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')  }
       res = ikea.post("/rsunify/app/basepackInformation/uploadFile", files = files ).text 
       print("Basepack uploaded") 
    else : 
       print("Nothing to upload basepack") 

    ##Start Beat Export and Order Sync after basepack uploaded
    export_data = {"fromDate":today_str,"toDate":today_str}
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
    while True : 
          status = ikea.post("/rsunify/app/quantumExport/getExportStatus",{"processId": export_num}).json()
          if str(status) == str(["0","0","1"]) : #comparing two lists
            print("Beat Export Completed")
            break 
          time.sleep(5)
          ikea.logger.debug(f"Waiting for beat export to be completed")
    ikea.post("/rsunify/app/sfmIkeaIntegration/callSfmIkeaIntegrationSync")
    ikea.post("/rsunify/app/api/callikeatocommoutletcreationallapimethods")
    sync_status = ikea.post("/rsunify/app/fileUploadId/upload").text.split("$del")[0]
    ikea.logger.debug(f"Order Sync (Basepack) status : {sync_status}")
    ##Export completed

    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="' + f"basepack_{today}.xlsx" + '"'
    return response

class VehicleForm(forms.Form):
        vehicle_name = forms.ModelChoiceField(
            queryset=models.Vehicle.objects.all(),
            empty_label="Select a vehicle",
            to_field_name='name', 
            label='Choose a vehicle'
        )
        type = forms.ChoiceField(choices=(("loading","Out For Delivery"),("delivery_success","Successful Delivered"),
                                          ("delivery_failed","Failed Delivered")),initial="loading",required=False)

def scan_bills(request) : 
    form = VehicleForm() 
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            selected_vehicle = form.cleaned_data['vehicle_name']
            type = form.cleaned_data['type']
            return render(request, 'scanner.html', {'selected_vehicle': selected_vehicle , "type" : type})
    return render(request, 'vehicle_selection.html', {'form': form})
    

def get_bill_out(request,loading_date = None):
    loading_date = loading_date or datetime.date.today() 
    vehicle = request.GET.get('vehicle')
    qs = models.Bill.objects.filter(loading_time__date = loading_date , vehicle = vehicle)
    bills = list(qs.filter(loading_sheet__isnull=True).values_list("loading_time","bill_id","bill__party__name"))
    ls = list(set(qs.filter(loading_sheet__isnull=False).values_list("loading_time","loading_sheet","loading_sheet__party")))
    sorted_all_bills = sorted(bills + ls, key=lambda x: x[0], reverse=True)
    sorted_all_bills = [ (bill,party) for time,bill,party in sorted_all_bills ] 
    return JsonResponse({"bills" : sorted_all_bills ,  
                          "total_count":len(sorted_all_bills) ,"bill_count":len(bills),"loading_sheet_count":len(ls)})

def get_bill_in(request,delivery_date = None):
    delivery_date = delivery_date or datetime.date.today() 
    vehicle = request.GET.get('vehicle')
    last_loading_date = models.Bill.objects.filter(loading_time__date__lt = delivery_date , vehicle = vehicle).order_by("-loading_time").first().loading_time
    bill_out_data = json.loads( get_bill_out(request,last_loading_date).content.decode('utf-8') )
    loaded_bills = [ tuple(i) for i in bill_out_data["bills"] ] 


    qs = models.Bill.objects.filter(delivered_time__date__gte =  delivery_date , vehicle = vehicle)
    bills = list(qs.filter(loading_sheet__isnull=True).values_list("loading_time","bill_id","bill__party__name"))
    ls = list(set(qs.filter(loading_sheet__isnull=False).values_list("loading_time","loading_sheet","loading_sheet__party")))
    sorted_all_bills = sorted(bills + ls, key=lambda x: x[0] or datetime.datetime(2024,4,1,0,0,0), reverse=True)
    sorted_all_bills = [ (bill,party) for time,bill,party in sorted_all_bills ] 
    delivered_bills = sorted_all_bills
    
    missing_bills = list(set(loaded_bills) - set(delivered_bills))

    return JsonResponse({ "bills" : missing_bills, "loading_date": last_loading_date.strftime("%d %b %Y"),
                          "missing_count":len(missing_bills) , "loading_count":len(loaded_bills), 
                          "delivery_previous_day_count":len(set(delivered_bills) & set(loaded_bills)) , "delivery_other_day_count" : len(set(delivered_bills)- set(loaded_bills)) })


def get_bill_data(request):
    if request.method == 'POST':
        data = request.POST.get('data')
        data = json.loads(data)
        inum = data.get("inum").upper()
        if len(inum) == 5 : inum = "A" + inum 
        vehicle = data.get("vehicle")
        bill_type = data.get("type")
        delivery_reason = data.get("delivery_reason")
        failure_reason = request.FILES.get("audio")

        extra_txt = ""
        configs = {
            "loading": {"update_fields": {"vehicle_id": vehicle, "loading_time": datetime.datetime.now()}},
            "delivery_success": {"update_fields": {"vehicle_id": vehicle, "delivered": True, "delivered_time": datetime.datetime.now(),
                                                   "delivery_reason": delivery_reason }},
            "delivery_failed": {"update_fields": {"vehicle_id": vehicle, "delivered": False, "delivered_time": datetime.datetime.now()}}
        }

        if inum.startswith("SM"):
            s = models.SalesmanLoadingSheet.objects.filter(inum=inum).first()
            extra_txt = "\n\nLoading Sheet Bills :\n" + "\n".join(s.bills.all().values_list("bill_id", flat=True))
            models.Bill.objects.filter(loading_sheet_id=inum).update(**configs[bill_type]["update_fields"])
        else:
            s = models.Sales.objects.filter(inum=inum).first()
            models.Bill.objects.filter(bill_id=inum).update(**configs[bill_type]["update_fields"])

        if failure_reason:
            audio_path = f"voice_notes/{inum}_delivery_failure.ogg"
            with open(audio_path, 'wb+') as destination:
                for chunk in failure_reason.chunks():
                    destination.write(chunk)

        data = [str(s.inum), str(s.party), str(s.beat), s.date.strftime('%d-%b-%Y')]
        return JsonResponse({"data": "\n".join(data) + extra_txt})

    return redirect("vehicle_selection")

def get_party_outstanding(request):
    party = request.GET.get('party')
    beat = request.GET.get('beat',None)
    qs = models.Outstanding.objects.filter(party_id = party).filter(balance__lte = -1)
    if beat : qs = qs.filter(beat = beat)
    return JsonResponse([{ "inum" : i.inum, "balance" : abs(i.balance), "days" : (datetime.date.today() - i.date).days , "beat" : i.beat }  for i in qs.all() ],
                        safe=False)


def salesman_cheque_entry_view(request):
    salesman = _salesman = request.GET.get('salesman',None)

    if salesman is None : 
        salesmans = models.Beat.objects.values_list('salesman_name', flat=True).distinct()
        class SalesmanForm(forms.Form):
            salesman = forms.ChoiceField( choices = zip(salesmans,salesmans) , label="Select Salesman")
        return render(request, 'salesman_cheque/salesman_select.html', {'form': SalesmanForm()})
    
    if request.method == "GET" : 
        beats = models.Beat.objects.filter(salesman_name=salesman,days__contains = 'friday').values_list('name', flat=True)
        parties = models.Outstanding.objects.filter(beat__in=beats).filter(balance__lte=-1).values_list('party__code',"party__name").distinct()
        cheques = models.SalesmanCollection.objects.filter(salesman=salesman,date=datetime.date.today()).values_list('party__name','amt')
        class EntryForm(forms.Form):
            party = forms.ChoiceField(
                choices= (("",""),) + tuple(parties) ,
                label="Party",
                required=True,
            )
            type = forms.ChoiceField(
                choices=[('cheque', 'Cheque'), ('neft', 'NEFT')],
                label="Entry Type",
                required=True
            )
            total_amount = forms.DecimalField(
                max_digits=10,
                decimal_places=2,
                label="Total Amount",
                widget=forms.NumberInput(attrs={
                    'placeholder': 'Enter total amount'
                }),
                required=True
            )
            cheque_date = forms.DateField(
                widget=forms.DateInput(attrs={
                    'type': 'date',
                    'placeholder': 'Select cheque date'
                }),
                label="Cheque Date",
                required=True
            )
            salesman = forms.CharField(widget=forms.HiddenInput(),initial=_salesman)
        return render(request, 'salesman_cheque/entry_form.html', {'form': EntryForm(), "cheques" : cheques })
    else : 
        party = request.POST.get("party")
        bills = models.Outstanding.objects.filter(party_id=party).filter(balance__lte=-1).values_list('inum',flat=True)
        return render(request, 'salesman_cheque/bill_entry.html', { "bills" : bills , "previous_form_data" : request.POST })

def add_salesman_cheque(request) : 
    salesman = request.POST.get("salesman")
    party = request.POST.get("party")
    entry_type = request.POST.get("type")
    total_amount = int(request.POST.get("total_amount"))
    cheque_date = datetime.datetime.strptime(request.POST.get("cheque_date"),"%Y-%m-%d").date()
    bills = request.POST.getlist("bill_no")
    amts = [ int(amt) for amt in request.POST.getlist("amount") ]
    if abs(sum(amts)-total_amount) > 10 : return JsonResponse("Amounts do not match",safe=False)
    chq_obj = models.SalesmanCollection.objects.create(date=cheque_date,amt=total_amount,type=entry_type,
                                             salesman=salesman,party_id = party)
    chq_obj.save()
    for bill,amt in zip(bills,amts) :
        models.SalesmanCollectionBill.objects.create(inum_id=bill,amt=amt,chq=chq_obj).save()
    return redirect(f"salesman_cheque/?salesman={salesman}")


def force_sales_sync(request) :
    sync_reports(limits={"sales":None} , 
                                min_days_to_sync={"collection":15})

def reload_server_view(request) : 
    reload_server()
    return JsonResponse(mark_safe("Server Restarted Successfully. Go to previous"),safe=False)



class ScanPendingBills(View):

    def change_status_to_checked_for_zero_outstanding(self,queryset) : 
        qs = models.Outstanding.objects.filter(inum__in =queryset.values_list("bill_id",flat=True))
        zero_outstanding_bills = qs.filter(balance__gte = -1).values_list("inum",flat=True)
        queryset.filter(bill_id__in = zero_outstanding_bills).update(outstanding_on_bill = 0,outstanding_on_sheet = 0)
        return zero_outstanding_bills
    
    def get(self, request):
        bill_no = request.GET.get("bill",None)
        sheet_no = request.GET.get("sheet",None)
        date = request.GET.get("date",None)

        if bill_no : 
            obj = models.PendingSheetBill.objects.get(sheet_id=sheet_no,bill_id=bill_no)
            obj.outstanding_on_ikea = -round(models.Outstanding.objects.get(inum=bill_no).balance)
            loading_sheet_or_bill_no =  models.Bill.objects.get(bill_id = bill_no).loading_sheet_id or bill_no #To verify scanner
            context = { "obj":obj ,
                        "party_name":str(obj.bill.party),
                        "bill_amt" : round(-obj.bill.amt) , 
                        "is_loading_sheet" : loading_sheet_or_bill_no != bill_no ,  
                        "loading_sheet_or_bill_no" : loading_sheet_or_bill_no}
            return render(request, 'scan_pending_bill/pending_bill.html',context)
        
        elif sheet_no : 

            if sheet_no and not sheet_no.startswith('PS'):
                sheet_no = 'PS' + sheet_no  # Add PS prefix if not present

            
            queryset = models.PendingSheetBill.objects.filter(sheet_id=sheet_no).all()
            self.change_status_to_checked_for_zero_outstanding(queryset)
            bills_info = [(obj.bill, obj.bill.party.name , obj.sheet_id , (obj.bill_status is None) or (obj.bill_status == "scanned") , obj.status()) for obj in queryset]
            return render(request, 'scan_pending_bill/select_pending_bill.html', {'bills': bills_info,"extra_script" :""})

        elif date : 
            date = datetime.datetime.strptime(date,"%Y-%m-%d")
            sheets = models.PendingSheet.objects.filter(date = date).all()
            queryset = models.PendingSheetBill.objects.filter(sheet__in=sheets).all()
            zero_outstanding_bills = self.change_status_to_checked_for_zero_outstanding(queryset)
            bills_info = [(obj.bill, obj.bill.party.name , obj.sheet_id , (obj.bill_status is None) or (obj.bill_status == "scanned") ,  obj.status() ) for obj in queryset]
            bills_info = sorted(bills_info,key=lambda x : x[4])
            
            checked = sum([ i[4] for i in bills_info ])
            not_checked= len(bills_info) - checked 
            zero_outstanding = len(zero_outstanding_bills)
            cheque_neft = queryset.filter(payment_mode__in = "cheque/neft").count()
            resaon_counts = queryset.exclude(Q(bill_status__isnull = True) | Q(bill_status = "scanned")).values("bill_status").annotate(count = Count("bill_status"))

            resaon_counts = [ (row["bill_status"].replace("_"," ").capitalize() , row["count"]) for row in resaon_counts if row["count"]]
            resaon_counts.sort(key = lambda x : x[1],reverse=True)
            resaon_counts = [("Cheque",cheque_neft )] + resaon_counts + [("Zero Outstanding Bills",zero_outstanding)]
            
            alert_text = [("Not Checked Bills",not_checked), ("Checked Bills",checked), ("\\nBreakup of Checked Bills","\\n")]
            for reason,value in resaon_counts : alert_text.append((reason,value))

            alert_text = "\\n".join( f"{k}: {v}" for k,v in alert_text )
            extra_script = mark_safe(f"window.alert('{alert_text}')")
            return render(request, 'scan_pending_bill/select_pending_bill.html', {'bills': bills_info , "extra_script" : extra_script})
        else :
            yesterday = datetime.date.today() - datetime.timedelta(days=0)
            recent_dates = [yesterday - datetime.timedelta(days=i) for i in range(4)]
            return render(request, 'scan_pending_bill/select_pending_sheet.html',{"recent_dates" : recent_dates})

    def post(self, request):
        # Extract pending sheet number from POST request
        pending_sheet_no = request.POST.get('pending_sheet_number')
        bill_no = request.POST.get('bill_number')
        bill_no = bill_no.split("(")[0].strip() #Remove the loading sheet number
        obj = models.PendingSheetBill.objects.get(sheet_id=pending_sheet_no,bill_id=bill_no)
        obj.payment_mode = request.POST.get('payment_mode')
        obj.outstanding_on_sheet = request.POST.get('outstanding_on_sheet')
        obj.outstanding_on_bill = request.POST.get('outstanding_on_bill')
        obj.bill_status = request.POST.get('bill_status')
        obj.save()
        return redirect(f"/scan_pending_bills?sheet={pending_sheet_no}")
        
def sync_impact(request):
    bill_counts = {}
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    yesterday_bills = models.Bill.objects.filter(bill__date = yesterday)
    for vehicle in models.Vehicle.objects.all(): 
        qs = models.Bill.objects.filter(loading_time__date = datetime.date.today(),vehicle = vehicle)
        bills = qs.values_list("bill_id",flat=True)
        beats = qs.values_list("bill__beat",flat=True)
        for beat in beats : 
            beat_all_bills_count = yesterday_bills.filter(bill__beat = beat).count()
            beat_loaded_bills_count = qs.filter(bill__beat = beat, bill__date = yesterday).count()
            print( beat, beat_all_bills_count , beat_loaded_bills_count )
            
        from_date = qs.aggregate(min_date = models.Min('bill__date'))['min_date']
        to_date = datetime.date.today() 
        if bills :
            bill_counts[vehicle.name] = len(bills)
            if vehicle.name_on_impact is None : 
                raise Exception("Vehicle name on impact is not set") 
            Billing().sync_impact(from_date,to_date,bills,vehicle.name_on_impact)
    return JsonResponse(bill_counts)


##depricated
class ManualPrintForm(forms.Form):
    from_bill = forms.CharField(label='From Bill', max_length=100)
    to_bill = forms.CharField(label='To Bill', max_length=100)

##depricated
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


