from typing import Iterable, Optional
from django.db import models
from django.db.models import CharField,IntegerField,FloatField,ForeignKey,DateField
from django.db.models import Sum,F

## Billing Models
class Billing(models.Model) : 
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True,blank=True)
    status = models.IntegerField()
    error = models.TextField(max_length=100000,null=True,blank=True)
    start_bill_no = models.TextField(max_length=10,null=True,blank=True)
    end_bill_no = models.TextField(max_length=10,null=True,blank=True)
    bill_count = models.IntegerField(null=True,blank=True)

    def __str__(self) -> str:
        return str(self.start_time.strftime("%d/%m/%y %H:%M:%S"))
     
class PushedCollection(models.Model) : 
    billing = models.ForeignKey(Billing,on_delete=models.CASCADE,related_name="collection")
    party_code = models.TextField(max_length=30)

class Orders(models.Model) : 
    
    order_no = models.TextField(max_length=60,primary_key=True)
    salesman = models.TextField(max_length=30)
    date = 	models.DateField()
    type = models.TextField(max_length=15,choices=(("SH","Shikhar"),("SE","Salesman")),blank=True,null=True)
    billing = models.ForeignKey(Billing,on_delete=models.CASCADE,related_name="orders",null=True,blank=True)
    party = models.ForeignKey("app.Party",on_delete=models.DO_NOTHING,related_name="orders",null=True,blank=True)
    beat = models.ForeignKey("app.Beat",on_delete=models.DO_NOTHING,related_name="orders",null=True,blank=True)
    place_order = models.BooleanField(default=False,db_default=False)
    force_order = models.BooleanField(default=False,db_default=False)
    creditlock = models.BooleanField(default=False,db_default=False)
    release = models.BooleanField(default=False,db_default=False)
    delete = models.BooleanField(default=False,db_default=False)
    # partial = models.BooleanField(default=False,db_default=False)

    def bill_value(self) : 
        return round( sum([ (p.quantity - p.allocated) * p.rate for p in self.products.all() ])   , 2 )

    def allocated_value(self) : 
        return round( sum([ p.allocated * p.rate for p in self.products.all() ]) or 0  , 2 )

    def partial(self) : 
        return bool( (self.products.filter(allocated = 0).count() and self.products.filter(allocated__gt = 0).count()) )  

    def __str__(self) -> str:
         return self.order_no
    
    class Meta : 
        verbose_name = 'Orders'
        verbose_name_plural = 'Billing'

class OrdersProxy(Orders):
    class Meta:
        proxy = True
        verbose_name = "order"

class OrderProducts(models.Model) : 
    order = models.ForeignKey(Orders,on_delete=models.CASCADE,related_name="products")
    product = models.TextField(max_length=100)
    batch = models.TextField(max_length=10,default="00000",db_default="00000")
    quantity =  models.IntegerField()
    allocated =  models.IntegerField()
    rate = models.FloatField()
    reason = models.TextField(max_length=50)
    # billed = models.BooleanField(default=False,db_default=False)
    
    def __str__(self) -> str:
         return self.product
    
    class Meta:
        unique_together = ('order', 'product','batch')

class BillStatistics(models.Model) : 
    type = models.TextField(max_length=30)	
    count = models.TextField(max_length=30) 

class ProcessStatus(models.Model) : 
    billing = models.ForeignKey(Billing,on_delete=models.CASCADE,related_name="process_status",null=True)
    status = models.IntegerField(default=0)
    process = models.TextField(max_length=30)	
    time = models.FloatField(null=True,blank=True) 
    

## Models For Accounting
## Abstract models

class PartyVoucher(models.Model) : 
      inum = CharField(max_length=20,primary_key=True)
      party = ForeignKey("app.Party",on_delete=models.DO_NOTHING,null=True)
      date = DateField()
      amt = FloatField(null=True)
      columns = ["inum","party_id","date","amt"]

      def __str__(self) -> str:
            return self.inum

      class Meta : 
            abstract = True 

class GstVoucher(models.Model) : 
      ctin = CharField(max_length=20,null=True,blank=True)
      irn = CharField(max_length=80,null=True,blank=True)
      gst_period = CharField(max_length=12,null=True,blank=True)
      
      @property
      def txval(self) : 
          return abs( round( self.invs.aggregate(s = Sum(F("txval")))["s"],3) )
      
      @property
      def tax(self) : 
          return abs( round( self.invs.aggregate(s = Sum(F("txval") * F("rt") / 100 ))["s"],3) )

      class Meta : 
            abstract = True 

class Party(models.Model) : 
      code = CharField(max_length=10,primary_key=True)
      master_code = CharField(max_length=10,null=True,blank=True)
      name = CharField(max_length=30,null=True,blank=True)
      type = CharField(db_default="shop",max_length=10)
      addr = CharField(max_length=150,blank=True,null=True)
      pincode = IntegerField(blank=True,null=True)
      ctin = CharField(max_length=20,null=True,blank=True)
      phone = CharField(max_length=20,null=True,blank=True)
      hul_code = CharField(max_length=40,null=True,blank=True)

      def __str__(self) -> str:
            return self.name or self.code 
     
      class Meta : 
            verbose_name_plural = 'Party'

class Sales( PartyVoucher,GstVoucher ) :
      discount = FloatField(default=0,db_default=0)
      roundoff = FloatField(default=0,db_default=0)
      type = CharField(max_length=15,db_default="sales",null=True)
      tds = FloatField(default=0,db_default=0)
      tcs = FloatField(default=0,db_default=0)
      columns = PartyVoucher.columns + ["ctin","roundoff","type","discount","beat"]
      beat = models.TextField(max_length=40,null=True)
      class Meta:
        verbose_name_plural = 'Sales'

    #   def save(self,*args,**kwargs) :  
    #         old_obj = Sales.objects.get(inum = self.inum)
    #         if old_obj is not None : 
    #            if old_obj.ctin != self.ctin :
    #               change = GstChanges(inum_id = self.inum,old_ctin= old_obj.ctin , new_ctin = self.ctin , remarks = "CHANGED MANUAL" )
    #               change.save()
    #         else : 
    #            change = GstChanges(inum_id = self.inum,old_ctin= None , new_ctin = self.ctin , remarks = "ADDED MANUAL" )
    #            change.save()
    #         return super().save(*args,**kwargs)
        
    #   def delete(self,*args,**kwargs) :
    #       change = GstChanges(inum_id = self.inum,old_ctin= None , new_ctin = None , remarks = "DELETED MANUAL" )
    #       change.save()
    #       return super().delete(*args,**kwargs)

class Collection( PartyVoucher ) : 
      bill = ForeignKey("app.Sales",db_index=False,db_constraint=False,on_delete=models.DO_NOTHING)
      mode = CharField(max_length=30)
      columns = ["inum","date","amt"] + ["bill_id","mode","party_id"]

      @property
      def Mode(self) : return (self.mode or "").upper()
      
      class Meta : 
            verbose_name_plural = 'Collection'

class Adjustment( PartyVoucher ) : 
      inum = CharField(max_length=20)
      from_bill = ForeignKey("app.Sales",db_index=False,db_constraint=False,on_delete=models.DO_NOTHING,related_name="adjusted_from")
      to_bill = ForeignKey("app.Sales",db_index=False,db_constraint=False,on_delete=models.DO_NOTHING,related_name="adjusted_to")
      adj_amt = FloatField(default=0)
      columns = PartyVoucher.columns + ["from_bill_id","to_bill_id","adj_amt"]
      class Meta : 
            unique_together = ("inum","from_bill","to_bill")
            verbose_name_plural = 'Adjustment'

class OpeningBalance(models.Model) : 
      party = ForeignKey("app.Party",on_delete=models.CASCADE)
      inum = CharField(max_length=20,primary_key=True)
      amt = FloatField(blank=True,null=True)
      beat = models.TextField(max_length=40)

class Beat(models.Model) : 
     id = IntegerField(primary_key=True)
     name = models.TextField(max_length=40)
     salesman_id = IntegerField()
     salesman_code = IntegerField()
     salesman_name = IntegerField()
     days = models.TextField(max_length=40)
     plg = models.TextField(max_length=15)
     def __str__(self) -> str:
          return self.name 

# class BeatMapping(models.Model) :  pass

class Outstanding(models.Model) : 
      party = ForeignKey("app.Party",on_delete=models.CASCADE)
      inum = CharField(max_length=20,primary_key=True)
      balance = FloatField(blank=True,null=True)
      beat = models.TextField(max_length=40)
      date = DateField()
      
      def __str__(self) -> str:
           return self.inum #+ "-" + self.party.name
      
      class Meta : 
            managed = False 
            verbose_name_plural = 'Outstanding'
            
## GST & Einvoice Related Models

# class Einv(models.Model) : 
#       bill = models.OneToOneField("app.Sales",on_delete=models.CASCADE,related_name="signed_json",db_constraint=False)
#       json = models.TextField()

# class GstChanges(models.Model) : 
#       inum = ForeignKey("app.Sales",on_delete=models.CASCADE,db_constraint=False,db_column="inum")
#       old_ctin = CharField(null=True,blank=True,max_length=20)
#       new_ctin = CharField(null=True,blank=True,max_length=20)
#       remarks = CharField(null=True,blank=True,max_length=40)
#       class Meta:
#         verbose_name_plural = 'GST-Changes'


## Collection Models
class Bank(models.Model) : 
    date = models.DateField()
    idx = models.IntegerField()
    id = models.CharField(max_length=15,primary_key=True)
    ref = models.TextField(max_length=200)
    desc = models.TextField(max_length=200)
    amt = models.IntegerField()
    bank = models.TextField(max_length=20)
    type = models.TextField(max_length=15,choices=(("cheque","Cheque"),("neft","NEFT"),("cash","Cash Deposit"),("others","Others")),null=True)
    pushed = models.BooleanField(db_default=False,default=False)
    class Meta : 
        unique_together = ('date','idx','bank')
        verbose_name_plural = 'Bank'

class BankCollection(models.Model) : 
      bill = ForeignKey("app.Outstanding",db_index=False,db_constraint=False,on_delete=models.DO_NOTHING)
      cheque = ForeignKey("app.Bank",related_name="collection",db_index=False,db_constraint=False,on_delete=models.DO_NOTHING)
      amt = models.IntegerField()
      entry_date = models.DateField(auto_now_add=True)
      coll_code = models.TextField(max_length=30,null=True,blank=True)
      class Meta:
          unique_together = ('bill', 'cheque')
      
class Sync(models.Model):
    process = models.CharField(max_length=20,primary_key=True)
    time = models.DateTimeField()