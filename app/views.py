# views.py
import datetime
from io import BytesIO
import json
import time
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
from openpyxl import load_workbook

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



