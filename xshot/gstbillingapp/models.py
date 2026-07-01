from django.db import models
from django.contrib.auth.models import User

from datetime import datetime
# Create your models here.

# ========================== Saas Data models ==================================

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    business_title = models.CharField(max_length=100, blank=True, null=True)
    business_address = models.TextField(max_length=400, blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    business_phone = models.CharField(max_length=20, blank=True, null=True)
    business_gst = models.CharField(max_length=15, blank=True, null=True)

    

    

    def __str__(self):
        return self.user.username


class Plan(models.Model):
    plan_name = models.TextField(max_length=20, blank=True, null=True)
    plan_value = models.IntegerField(blank=True, null=True)
    monthly_invoice_limit = models.IntegerField(blank=True, null=True)


class BillingProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, blank=True, null=True, on_delete=models.SET_NULL)
    plan_start_date = models.DateField(blank=True, null=True)
    plan_end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.user.username

# ======================= gstbillingapp Data models =================================

class Customer(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    customer_name = models.CharField(max_length=200)
    customer_address = models.TextField(max_length=600, blank=True, null=True)
    customer_phone = models.CharField(max_length=14, blank=True, null=True)
    customer_gst = models.CharField(max_length=15, blank=True, null=True)
    customer_pan = models.CharField(max_length=15, blank=True, null=True)
    def __str__(self):
        return self.customer_name

ACCOUNT_TYPE_CHOICES = [
    ('savings', 'Savings Account'),
    ('current', 'Current Account'),
    ('salary', 'Salary Account'),
    ('fixed_deposit', 'Fixed Deposit Account'),
    ('recurring_deposit', 'Recurring Deposit Account'),
    ('nro', 'NRO Account'),
    ('nre', 'NRE Account'),
    ('others', 'Others'),
]
class BankDetails(models.Model):
    bank_name = models.CharField(max_length=255)
    account_holder_name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=50, blank=True, null=True)

    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    branch_name = models.CharField(max_length=255)
    address = models.TextField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    account_type = models.CharField(
    max_length=50,
    choices=ACCOUNT_TYPE_CHOICES,
    blank=True,
    null=True
)
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"



class Invoice(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    invoice_number = models.IntegerField()
    invoice_date = models.DateField()
    bank = models.ForeignKey(BankDetails, on_delete=models.SET_NULL, null=True, blank=True,default=None)
    invoice_customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,blank=True
    )
    invoice_customer_gst = models.CharField(max_length=15, blank=True, null=True)
    invoice_customer_phone = models.CharField(max_length=14, blank=True, null=True)
    
    invoice_amt_without_gst = models.FloatField()
    invoice_amt_igst = models.FloatField()
    invoice_amt_cgst = models.FloatField()
    invoice_amt_sgst = models.FloatField()
    invoice_amt_with_gst = models.FloatField()
    invoice_json = models.TextField()
    inventory_reflected = models.BooleanField(default=True)
    books_reflected = models.BooleanField(default=True)

    buyer_tin_number = models.CharField(max_length=20, blank=True, null=True,default=0)
    terms_and_conditions = models.TextField(blank=True, null=True,default=None)
    business_tin_number = models.CharField(max_length=20, blank=True, null=True,default=0)
    sup_pan_number = models.CharField(max_length=15, blank=True, null=True,default=0)  
    project_description = models.TextField(blank=True, null=True)
   

    def __str__(self):
        return str(self.invoice_number) + " | " + str(self.invoice_date)


class CreditNote(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    credit_note_number = models.IntegerField()
    credit_note_date = models.DateField()
    associated_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_notes')
    bank = models.ForeignKey(BankDetails, on_delete=models.SET_NULL, null=True, blank=True,default=None)
    credit_note_customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,blank=True
    )
    credit_note_customer_gst = models.CharField(max_length=15, blank=True, null=True)
    credit_note_customer_phone = models.CharField(max_length=14, blank=True, null=True)
    
    credit_note_amt_without_gst = models.FloatField()
    credit_note_amt_igst = models.FloatField()
    credit_note_amt_cgst = models.FloatField()
    credit_note_amt_sgst = models.FloatField()
    credit_note_amt_with_gst = models.FloatField()
    credit_note_json = models.TextField()

    buyer_tin_number = models.CharField(max_length=20, blank=True, null=True,default=0)
    terms_and_conditions = models.TextField(blank=True, null=True,default=None)
    business_tin_number = models.CharField(max_length=20, blank=True, null=True,default=0)
    sup_pan_number = models.CharField(max_length=15, blank=True, null=True,default=0)  
    project_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return str(self.credit_note_number) + " | " + str(self.credit_note_date)


class Product(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=200)
    product_hsn = models.CharField(max_length=50, null=True, blank=True)
    product_unit = models.CharField(max_length=50)
    product_gst_percentage = models.FloatField()
    product_rate_with_gst = models.FloatField()
    def __str__(self):
        return str(self.product_name)

# ========================= Inventory Data models ====================================
class InventoryLog(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    date = models.DateTimeField(default=datetime.now, blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True)
    change = models.IntegerField(default=0)
    CHANGE_TYPES = [
        (0, 'Other'),
        (1, 'Purchase'),
        (2, 'Production'),
        (4, 'Sales'),
    ]
    change_type = models.IntegerField(choices=CHANGE_TYPES, default=0)

    associated_invoice = models.ForeignKey(Invoice, blank=True, null=True, default=None, on_delete=models.SET_NULL)
    description = models.TextField(max_length=600, blank=True, null=True)

    def __str__(self):
        # Safely get product name
        product_name = getattr(self.product, 'product_name', 'No Product')
        
        # Safely get change amount
        change = str(self.change) if self.change is not None else '0'
        
        # Safely get description
        description = str(self.description) if self.description else 'No Description'
        
        # Safely get date
        date = str(self.date) if self.date else 'No Date'
        
        return f"{product_name} | {change} | {description} | {date}"

class Inventory(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    current_stock = models.IntegerField(default=0)
    alert_level = models.IntegerField(default=0)
    last_log = models.ForeignKey(InventoryLog, null=True, blank=True, default=None, on_delete=models.SET_NULL)

    def __str__(self):
        if self.product:  # Check if product exists
            return f"{self.product.product_name} | {self.current_stock}"
        return f"Inventory #{self.id} | {self.current_stock}"

# ========================= Books Data models ======================================

class Book(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
    current_balance = models.FloatField(default=0)
    last_log = models.ForeignKey('BookLog', null=True, blank=True, default=None, on_delete=models.SET_NULL)

    def __str__(self):
        return self.customer.customer_name if self.customer else "No Customer"


class BookLog(models.Model):
    parent_book = models.ForeignKey(Book, null=True, blank=True, on_delete=models.CASCADE)
    date = models.DateTimeField(default=datetime.now, blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True)
    CHANGE_TYPES = [
        (0, 'Paid'),
        (1, 'Purchased Items'),
        (2, 'Sold Items'),
        (4, 'Other'),
    ]
    change_type = models.IntegerField(choices=CHANGE_TYPES, default=0)
    change = models.FloatField(default=0.0)

    associated_invoice = models.ForeignKey(Invoice, blank=True, null=True, default=None, on_delete=models.SET_NULL)
    description = models.TextField(max_length=600, blank=True, null=True)

    def __str__(self):
        return self.parent_book.customer.customer_name + " | " + str(self.change) + " | " + self.description + " | " + str(self.date)

