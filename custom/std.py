from datetime import datetime , timedelta
import pandas as pd
from dateutil.relativedelta import relativedelta
import os 
from pymongo import MongoClient

def moc_range(fromd=datetime(2018,4,1),tod=datetime.now(),slash=False) :
    if type(fromd) == str : fromd = datetime.strptime(fromd,"%d%m%Y")
    if type(tod) == str : tod = datetime.strptime(tod,"%d%m%Y")
    
    fromd -= timedelta(days=21)
    tod -= timedelta(days=21) 
    tod += relativedelta(day=31)
    return [ (dt + relativedelta(months=1)).strftime(f"%m{'/' if slash else ''}%Y") for dt in pd.date_range(fromd,tod,freq="1M").to_list() ]

def month_range(fromd,tod,slash=False) : 
    fromd = datetime.strptime(fromd,"%m%Y")
    tod = datetime.strptime(tod,"%m%Y")
    return [ dt.strftime(f"%m{'/' if slash else ''}%Y") for dt in pd.date_range(fromd,tod,freq="MS").to_list() ]

def sync_db() : 
    c1 = MongoClient("mongodb+srv://venkatesh2004:venkatesh2004@cluster0.9x1ccpv.mongodb.net/?retryWrites=true&w=majority")
    c2 = get_mongo()
    c2["demo"]["test_users"].delete_many({})
    c2["demo"]["test_users"].insert_many( list(c1["demo"]["test_users"].find()) )
    return 

def get_mongo() : 
    import subprocess 
    if subprocess.getoutput("systemctl is-active  mongod.service") == "inactive" :
       print("Mongo Service To be started...") 
       os.system("sudo systemctl start mongod.service")
    return MongoClient()

def m2d(str,end=False) :
    d = datetime.strptime(str,"%m%Y") 
    if end : return d +pd.tseries.offsets.MonthEnd(0)
    return d 
     
def gst_date_filter_func(k,fromd:datetime,tod:datetime) :
    t = {"b2b":"idt","cdnr":"nt_dt"}
    if k in t :
        def dt_filter(df): 
            _t = pd.to_datetime(df[t[k]],format="%d-%m-%Y")
            return df[ (fromd <= _t ) & ( _t <= tod) ]
        return dt_filter
    return lambda df : df 

def columnless_concat(dfs,columns) : 
    for df in dfs : df.columns = columns 
    return pd.concat(dfs,axis=0)

    
def get_args(keys,desc="") :
    import argparse 
    std_args = {"fromd":lambda d: datetime.strptime(d, '%Y%m%d'),"tod":lambda d: datetime.strptime(d, '%Y%m%d'), 
                "user":str}
    # Initialize parser
    parser = argparse.ArgumentParser()
    parser.description = desc
    for key in keys : 
        if key in std_args : parser.add_argument(key,type=std_args[key])
        else : 
            parser.add_argument(key)
    args = parser.parse_args() 
    return ( args.__dict__[key] for key in keys ) 