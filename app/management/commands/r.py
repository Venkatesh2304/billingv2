import pandas as pd
import json
import re
from datetime import datetime
from custom.classes import IkeaDownloader
print( IkeaDownloader().download_settle_cheque("ALL",fromd=datetime(2024,12,1)) )
sdf 

# Load the Excel file
data_path = 'eway_ikea1.xlsx'
eway_data = pd.read_excel(data_path)

def validate_gstin(gstin):
    """Validate GSTIN format."""
    return bool(re.match(r'^\d{2}[A-Z]{3}[A-Z0-9]{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}$', gstin))

def format_date(date):
    """Format date to dd/mm/yyyy."""
    return date.strftime('%d/%m/%Y')

def validate_doc_no(doc_no):
    """Validate Document Number."""
    return len(doc_no) <= 16

# Apply basic validation and transformation
# eway_data['From_GSTIN'] = eway_data['From_GSTIN'].apply(lambda x: x if validate_gstin(x) else None)
eway_data['Doc date'] = eway_data['Doc date'].apply(format_date)
eway_data['Doc.No'] = eway_data['Doc.No'].apply(lambda x: x if validate_doc_no(x) else None)
eway_data["CGST Rate"] = eway_data["Tax Rate"].str.split("+").str[0]
eway_data["SGST Rate"] = eway_data["Tax Rate"].str.split("+").str[1]
eway_data["To_Pin_code"] = eway_data["To_Pin_code"].fillna(620010)
eway_data["Distance level(Km)"] = 3
eway_data["Vehicle No"] = "TN47T8357"




grouped = eway_data.groupby('Doc.No')

# Prepare JSON
eway_json = {
    "version": "1.0",
    "billLists": []
}

for doc_no, group in grouped:
    if doc_no is None:
        continue
    bill_json = {
        "userGstin": group['From_GSTIN'].iloc[0],
        "supplyType": "O",
        "subSupplyType": 1,
        "docType":  "INV" , #group['Doc type'].iloc[0],
        "docNo": doc_no,
        "docDate": group['Doc date'].iloc[0],
        "transType": 1,
        "fromGstin": group['From_GSTIN'].iloc[0],
        "fromPincode": int(group['From_pin_code'].iloc[0]),  # Corrected column name
        "fromStateCode": 33 ,  # Corrected column name
        "actualFromStateCode": 33 ,  # Assuming this maps to the same state code
        "toGstin": group['To_GSTIN'].iloc[0],
        "toPincode": int(group['To_Pin_code'].iloc[0]),  # Corrected column name
        "toStateCode": 33 ,  # Corrected column name
        "actualToStateCode": 33,  # Assuming this maps to the same state code
        "totInvValue": float(group['Total Amount'].sum()),
        "transDistance": int(group['Distance level(Km)'].iloc[0]),
        "vehicleNo": group['Vehicle No'].iloc[0],
        "itemList": []
    }
    
    for _, item in group.iterrows():
        item_json = {
            "hsnCode": item['HSN'],
            "units": item['Units'],
            "quantity": float(item['Qty']),
            "taxableAmount": round(float(item['Assessable Value']),2),
            "cgstRate": float(item['CGST Rate']),
            "sgstRate": float(item['SGST Rate']),
            "igstRate": 0 ,
            "cessRate": 0 ,
            "totalAmount": round(float(item['Total Amount']),2) 
        }
        bill_json['itemList'].append(item_json)
    
    eway_json['billLists'].append(bill_json)

# Output to JSON file
json_output_path = 'final_eway_bill.json'
with open(json_output_path, 'w') as file:
    json.dump(eway_json, file, indent=4)

print("JSON file has been created successfully at:", json_output_path)
