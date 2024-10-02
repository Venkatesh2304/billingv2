from collections import defaultdict
import glob
import json
import re
import time
from django.db import connection
import pandas as pd
from app.models import *
import warnings
warnings.filterwarnings("ignore")

# for file in glob.glob("custom/curl/**/*.txt", recursive=True) : 
#     save_request(file)

# exit(0)





# from custom.classes import IkeaDownloader

# html = IkeaDownloader().get("https://leveredge18.hulcd.com/rsunify/app/rssmBeatPlgLink/loadRssmBeatPlgLink#!").text
# salesman_ids = re.findall(r"<input type=\"hidden\" value=\"([0-9]+)\" />",html,re.DOTALL)[::3] 
# salesman_names = pd.read_html(html)[0]["Salesperson Name"]
# print( dict(zip(map(int,salesman_ids),salesman_names)) )



# exit(0)


cur = connection.cursor()
cur.execute("DROP VIEW IF EXISTS app_outstanding_raw")
print( pd.read_sql(f"SELECT sum(balance) from app_outstanding where balance <= -1",connection) )
print( pd.read_sql(f"SELECT * from app_collection where bill_id = 'A41844' ",connection) )
print( pd.read_sql(f"SELECT * from app_adjustment where to_bill_id = 'A01589' order by date desc limit 20 ",connection) )
# cur.execute("DELETE from app_bank")
# cur.execute("DELETE from app_bankcollection")
exit(0)

df = pd.read_excel("beat.xlsx")
df["Old Beat Name"] = df["Old Beat Name"].str.strip().str.replace("&amp;","&")
for party,rows in df.groupby("Party Code") : 
    a = rows["Old Beat Name"].iloc[0].count(",") + 1 
    b = len(rows)
    x = set(rows["Old Beat Name"].iloc[0].split(", ")) 
    y = set(rows["New Beat Name"])
    if len(x & y) != len(x) : 
        print( x,y )
        input()
    if a != b :
         print(rows)
         input()
cur.execute("DELETE from app_bankcollection")
print( pd.read_sql(f"SELECT * from app_party where hul_code is NULL",connection) )
exit(0)
# cur.execute("DELETE from app_orderproducts")
# cur.execute("DELETE from app_orders")

print( pd.read_sql(f"SELECT * from app_openingbalance",connection) )

# cur.execute("CREATE INDEX idx_openingbalance_party_inum ON app_openingbalance (party_id, inum)")
# cur.execute("CREATE INDEX idx_sales_party_inum ON app_sales (party_id, inum)")
# cur.execute("CREATE INDEX idx_collection_party_bill ON app_collection (party_id, bill_id)")
# cur.execute("CREATE INDEX idx_adjustment_party_to_bill ON app_adjustment (party_id, to_bill_id)")

cur.execute("DROP VIEW IF EXISTS app_outstanding")
s = time.time()
cur.execute("""CREATE TABLE app_outstanding AS 
select party_id,inum,sum(amt) as balance , max(beat) as beat, min(date) as date from (
SELECT party_id,inum,'2023-04-01' as date,amt,beat from app_openingbalance
union all
SELECT party_id,inum,date,amt,beat from app_sales where type = 'sales'
union all
SELECT party_id,bill_id as inum,date,amt,NULL as beat from app_collection
union all
SELECT party_id,to_bill_id as inum,date,adj_amt as amt,NULL as beat from app_adjustment ) 
group by party_id,inum 
having abs(sum(amt)) > 1
""")
print( time.time() - s )
            
cur.execute("DROP VIEW IF EXISTS app_outstanding_raw")
cur.execute("""CREATE VIEW app_outstanding_raw AS 
select * from (
SELECT party_id,inum,'2023-04-01' as date,amt,beat from app_openingbalance
union all
SELECT party_id,inum,date,amt,beat from app_sales where type = 'sales'
union all
SELECT party_id,bill_id as inum,date,amt,NULL as beat from app_collection
union all
SELECT party_id,to_bill_id as inum,date,adj_amt as amt,NULL as beat from app_adjustment ) 
""")



print( pd.read_sql(f"SELECT * from outstanding where beat is NULL",connection) )
            
exit(0)
print( pd.read_sql(f"SELECT * from app_billing",connection) )
print( pd.read_sql(f"SELECT * from app_processstatus",connection) )
print( pd.read_sql(f"SELECT * from app_creditlock",connection) )
print( pd.read_sql(f"SELECT * from app_orders",connection) )
print( pd.read_sql(f"SELECT * from app_orderproducts",connection) )
cur.execute("update app_orderproducts set allocated = 3 where id = 1")
exit(0)