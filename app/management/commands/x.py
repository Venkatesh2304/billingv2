from collections import defaultdict
import datetime
import glob
import json
import re
import time
from django.db import connection
import pandas as pd
from app.models import *
import warnings
warnings.filterwarnings("ignore")
pd.options.display.float_format = '{:.2f}'.format
# for file in glob.glob("custom/curl/**/*.txt", recursive=True) : 
#     save_request(file)

# exit(0)





# from custom.classes import IkeaDownloader

# html = IkeaDownloader().get("https://leveredge18.hulcd.com/rsunify/app/rssmBeatPlgLink/loadRssmBeatPlgLink#!").text
# salesman_ids = re.findall(r"<input type=\"hidden\" value=\"([0-9]+)\" />",html,re.DOTALL)[::3] 
# salesman_names = pd.read_html(html)[0]["Salesperson Name"]
# print( dict(zip(map(int,salesman_ids),salesman_names)) )



# exit(0)
from app.models import Orders,OrderProducts

print( Orders.objects.filter(date  = datetime.date.today(),party__name="SRI MURUGAN STORES-ALWAR THOPE-D-D").all() )


cur = connection.cursor()
print( pd.read_sql(f"SELECT  * from app_outstandingraw where  inum = 'A09923' ",connection)  )
print( pd.read_sql(f"SELECT  * from app_collection where  bill_id = 'A00141' ",connection)  )
df = pd.read_sql(f"""select party_id as party ,inum,amt,Cast((days/7) as Integer)*7 as days from (SELECT party_id,inum , -amt as amt , date , 
Cast ((
    JulianDay((select max(date) from app_outstandingraw where inum=app_sales.inum)) - JulianDay(date)
) As Integer) as days 
from app_sales 
where amt < -300 )
where days !=0 """,connection)

df = df[df.days < 30]
df = pd.pivot_table(df,index="party",values=["inum"],columns=["days"],aggfunc={"inum":"count"}).fillna(0)
df = df[ df.sum(axis=1) > 10 ]
df = df.div( df.sum(axis=1) , axis= 0 ) 
print( df.idxmax(axis=1).value_counts() )
print( df[ df.max(axis=1) >= 0.5 ] )
print( df[ df.max(axis=1) < 0.5 ] )



print( df ) 
exit(0)

print(df)
print( df.groupby("days").aggregate({"amt" : "sum","inum" : "count"}).sort_values(by="inum",ascending=False) )

#and party_id = 'P15667'

# exit(0)
# cur.execute("DROP VIEW IF EXISTS app_outstandingraw")
# cur.execute("""CREATE VIEW app_outstandingraw AS 
# select * from (
# SELECT party_id,inum,'2024-03-31' as date,amt,beat from app_openingbalance
# union all
# SELECT party_id,inum,date,amt,beat from app_sales where type = 'sales'
# union all
# SELECT party_id,bill_id as inum,date,amt,NULL as beat from app_collection
# union all
# SELECT party_id,to_bill_id as inum,date,adj_amt as amt,NULL as beat from app_adjustment ) 
# """)


# cur.execute("DELETE from app_billing where date = '2024-10-07'")
# cur.execute("DELETE from app_orders where date = '2024-10-07'")
# print( pd.read_sql(f"SELECT  * from app_orders where order_no ='91SMN00001D-P122620241007' ",connection)  )
# print( pd.read_sql(f"SELECT  * from app_orders where date ='2024-10-07' and party_id = 'P15667' ",connection)  )
# cur.execute("DELETE from app_orderproducsts where date = '2024-10-07'")
exit(0)

a = pd.read_sql(f"SELECT inum,-balance as amt,(select name from app_party where code = party_id) from app_outstanding where balance <= -1",connection) 
b = pd.read_excel("o.xlsx").rename(columns={"Bill Number":"inum","O/S Amount":"amt1"}).iloc[:-1][["inum","amt1"]]
c = pd.merge(a,b,on="inum",how="outer").fillna(0)
c["d"]  = c.amt - c.amt1
print( c[c.d.abs() > 1] )


print( pd.read_sql(f"SELECT * from app_billing order by start_time desc  limit 20",connection) )
print( pd.read_sql(f"SELECT sum(amt) from app_collection where date >= '2024-04-01' and date < '2024-10-05'",connection) )

print( pd.read_sql(f"SELECT sum(balance) from app_outstanding where balance <= -1",connection) )
print( pd.read_sql(f"SELECT * from app_sales join app_party on party_id = code and date = '2024-10-05' ",connection).to_excel("a.xlsx") )
print( pd.read_sql(f"SELECT * from app_collection where bill_id ='A45150'",connection) )
print( pd.read_sql(f"SELECT * from app_party where name ='VARSHIKA MALIGAI'",connection) )
print( pd.read_sql(f"SELECT * from app_collection join app_party on party_id = code where name ='MATHINA STORE-D-D-D-D' and date = '2024-05-10'",connection) )


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