import os
from custom.classes import Billing
import pandas as pd
import datetime 

fromd = datetime.datetime(2019,9,21)
tod = datetime.datetime(2019,12,31)

def download(fb,tb,pdf_name) :
    billing = Billing()

    json_data = {
        'rtype': 'POST',
        'action': '/app/visualizer/rf/generate',
        'params': {
            'billFrom': fb ,
            'billTo': tb ,
            'reportType': 'pdf',
            'blhVatFlag': '2',
            'shade': 1,
            'pack': '10',
            'damages': None,
            'halfPage': 0,
            'bp_division': '',
            'salesMan': '',
            'party': '',
            'market': '',
            'planset': '',
            'fromDate': '',
            'toDate': '',
            'veh_Name': '',
            'printId': 0,
            'printerName': 'TVS MSP 250 Star',
            'Lable_position': 2,
            'billType': '2',
            'printOption': '0',
            'RptClassName': 'BILL_PRINT_REPORT',
            'reptName': 'billPrint',
            'RptId': '910',
            'freeProduct': 'Default',
            'shikharQrCode': None,
            'rptTypOpt': 'pdf',
            'gstTypeVal': '1',
            'billPrint_isPrint': 0,
            'units_only': 'Y',
            'report_id': 29,
            'template_id': 35,
            'bill_from': fb ,
            'bill_to': tb ,
            'bill_type': '2',
            'output_type': 'STREAM',
            'free_product': 'Default',
            'bill_from_date': '',
            'bill_to_date': '',
            'vehicle': '',
            'print_id': 0,
            'shikhar_qr_code': None,
        },
        'payload': {
            'billFrom': fb ,
            'billTo': tb ,
            'reportType': 'pdf',
            'blhVatFlag': '2',
            'shade': 1,
            'pack': '10',
            'damages': None,
            'halfPage': 0,
            'bp_division': '',
            'salesMan': '',
            'party': '',
            'market': '',
            'planset': '',
            'fromDate': '',
            'toDate': '',
            'veh_Name': '',
            'printId': 0,
            'printerName': 'TVS MSP 250 Star',
            'Lable_position': 2,
            'billType': '2',
            'printOption': '0',
            'RptClassName': 'BILL_PRINT_REPORT',
            'reptName': 'billPrint',
            'RptId': '910',
            'freeProduct': 'Default',
            'shikharQrCode': None,
            'rptTypOpt': 'pdf',
            'gstTypeVal': '1',
            'billPrint_isPrint': 0,
            'units_only': 'Y',
            'report_id': 29,
            'template_id': 35,
            'bill_from': fb,
            'bill_to': tb,
            'bill_type': '2',
            'output_type': 'STREAM',
            'free_product': 'Default',
            'bill_from_date': '',
            'bill_to_date': '',
            'vehicle': '',
            'print_id': 0,
            'shikhar_qr_code': None,
        },
        'entity': 'report',
        'task': 'REPORT_GENERATE',
        'page': 0,
        'data_type': 'json',
        'content_type': 'application/json; charset=utf-8',
        'cache': None,
        'processDt': None,
        'req_uid': None,
    }

    durl = billing.post(
        'https://leveredge18.hulcd.com/rsunify/app/visualizer/rf/generate',
        json=json_data
    ).json()["payload"]

    with open(pdf_name,"wb+") as f : 
        f.write( billing.get(f"https://leveredge18.hulcd.com/rsunify/app/visualizer/rf/report/stream?FILE={durl}").content )

def batch_bill_pdf() :
    dir = f"month_wise_{os.environ['user']}"
    url =  lambda f,t : f'/rsunify/app/commonPdfRptContrl/pdfRptGeneration?strJsonParams=%7B%22billFrom%22%3A%22{f}%22%2C%22billTo%22%3A%22{t}%22%2C%22reportType%22%3A%22pdf%22%2C%22blhVatFlag%22%3A2%2C%22shade%22%3A1%2C%22pack%22%3A%22910%22%2C%22damages%22%3Anull%2C%22halfPage%22%3A0%2C%22bp_division%22%3A%22%22%2C%22salesMan%22%3A%22%22%2C%22party%22%3A%22%22%2C%22market%22%3A%22%22%2C%22planset%22%3A%22%22%2C%22fromDate%22%3A%22%22%2C%22toDate%22%3A%22%22%2C%22veh_Name%22%3A%22%22%2C%22printId%22%3A0%2C%22printerName%22%3A%22TVS%2BMSP%2B250%2BStar%22%2C%22Lable_position%22%3A2%2C%22billType%22%3A2%2C%22printOption%22%3A%220%22%2C%22RptClassName%22%3A%22BILL_PRINT_REPORT%22%2C%22reptName%22%3A%22billPrint%22%2C%22RptId%22%3A%22910%22%2C%22freeProduct%22%3A%22Default%22%2C%22shikharQrCode%22%3Anull%2C%22rptTypOpt%22%3A%22pdf%22%2C%22gstTypeVal%22%3A%221%22%2C%22billPrint_isPrint%22%3A0%2C%22units_only%22%3A%22Y%22%7D'
    sales_reg = Billing().sales_reg(fromd,tod)
    sales_reg = sales_reg.rename(columns={"BillDate/Sales Return Date":"date"})
    sales_reg = sales_reg.dropna(subset="date")[sales_reg["Crd Sales"] != 0]
    sales_reg["month"] = pd.to_datetime(sales_reg["date"]).dt.strftime("%m_%Y")
    sales_reg["day"] = pd.to_datetime(sales_reg["date"]).dt.strftime("%d-%m-%Y")
    ## Download bills datewise && monthwise pdfs 
    os.makedirs(dir,exist_ok=True)
    os.chdir(dir)
    for month,rows in sales_reg.groupby("month") : 
        os.makedirs(month,exist_ok=True)
        for day,rows in rows.groupby("day") : 
            pdf_name = f"{month}/{day}.pdf"
            if os.path.exists(pdf_name) : continue 
            bills = list(rows["BillRefNo"])
            bills.sort()
            download( bills[0] , bills[-1]  , pdf_name )    
    os.chdir("..")

bills = ["A00001","A00005"]
download( bills[0] , bills[-1]  , "a.pdf" ) 
batch_bill_pdf()
