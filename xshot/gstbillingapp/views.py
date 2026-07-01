import datetime
import json
import num2words

from django.shortcuts import render
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.http import JsonResponse
from django.db.models import Max

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Customer
from .models import Invoice
from .models import Product
from .models import UserProfile
from .models import Inventory
from .models import InventoryLog
from .models import Book
from .models import BookLog


from .utils import invoice_data_validator 
from .utils import invoice_data_processor
from .utils import update_products_from_invoice
from .utils import update_inventory
from .utils import create_inventory
from .utils import add_customer_book
from .utils import auto_deduct_book_from_invoice
from .utils import remove_inventory_entries_for_invoice

from .forms import CustomerForm
from .forms import ProductForm
from .forms import UserProfileForm
from .forms import InventoryLogForm
from .forms import BookLogForm

from datetime import date
# Create your views here.


# User Management =====================================

@login_required
def user_profile_edit(request):
    context = {}
    user_profile = get_object_or_404(UserProfile, user=request.user)
    context['user_profile_form'] = UserProfileForm(instance=user_profile)
    
    if request.method == "POST":
        user_profile_form = UserProfileForm(request.POST, instance=user_profile)
        user_profile_form.save()
        return redirect('user_profile')
    return render(request, 'gstbillingapp/user_profile_edit.html', context)


@login_required 
def user_profile(request):
    context = {}
    user_profile = get_object_or_404(UserProfile, user=request.user)
    context['user_profile'] = user_profile
    return render(request, 'gstbillingapp/user_profile.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("invoice_create")
    context = {}
    auth_form = AuthenticationForm(request)
    if request.method == "POST":
        auth_form = AuthenticationForm(request, data=request.POST)
        if auth_form.is_valid():
            user = auth_form.get_user()
            if user:
                login(request, user)
                return redirect("invoice_create")
        else:
            context["error_message"] = auth_form.get_invalid_login_error()
    context["auth_form"] = auth_form
    return render(request, 'gstbillingapp/login.html', context)


def signup_view(request):
   # if request.user.is_authenticated:
   #     return redirect("invoice_create")
    context = {}
    signup_form = UserCreationForm()
    profile_edit_form = UserProfileForm()
    context["signup_form"] = signup_form
    context["profile_edit_form"] = profile_edit_form

    
    if request.method == "POST":
        signup_form = UserCreationForm(request.POST)
        profile_edit_form = UserProfileForm(request.POST)
        context["signup_form"] = signup_form
        context["profile_edit_form"] = profile_edit_form

        if signup_form.is_valid():
            user = signup_form.save()
        else:
            context["error_message"] = signup_form.errors
            return render(request, 'gstbillingapp/signup.html', context)
        if profile_edit_form.is_valid():
            userprofile = profile_edit_form.save(commit=False)
            userprofile.user = user
            userprofile.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect("invoice_create")



    return render(request, 'gstbillingapp/signup.html', context)



# Invoice, products and customers ===============================================

@login_required
def invoice_create(request):
    # Fetch bank details correctly
    banks = BankDetails.objects.all()

    today = date.today()
    inyear = today.strftime("%y")
    inmonth = today.strftime("%m")

    # Check if user profile has business info
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not user_profile.business_title:
        messages.error(request, "Please update your business title in your profile to create invoices.")
        return redirect('user_profile')  # or any other safe view

    context = {
        "banks": banks,
        "default_invoice_number": Invoice.objects.filter(user=request.user).aggregate(Max('invoice_number'))['invoice_number__max'],
        "default_invoice_date": datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d'),
    }

    if not context["default_invoice_number"]:
        invno = str(inyear) + str(inmonth) + str("001")
        context["default_invoice_number"] = invno
    else:
        temp = str(context["default_invoice_number"])
        if inyear != temp[:2] or inmonth != temp[2:4]:
            invno = str(inyear) + str(inmonth)
        else:
            context["default_invoice_number"] += 1

    if request.method == "POST":
        invoice_data = request.POST

        # Validate input
        validation_error = invoice_data_validator(invoice_data)
        if validation_error:
            context["error_message"] = validation_error
            return render(request, "gstbillingapp/invoice_create.html", context)

        # Process invoice data
        invoice_data_processed = invoice_data_processor(invoice_data)

       

        # Save customer
        customer = Customer.objects.filter(
            user=request.user,
            customer_name=invoice_data["customer-name"],
            customer_address=invoice_data["customer-address"],
            customer_phone=invoice_data["customer-phone"],
            customer_gst=invoice_data["customer-gst"],
            customer_pan=invoice_data["buyer_pan_number"]
        ).first()

        if not customer:
            customer = Customer(
                user=request.user,
                customer_name=invoice_data["customer-name"],
                customer_address=invoice_data["customer-address"],
                customer_phone=invoice_data["customer-phone"],
                customer_gst=invoice_data["customer-gst"],
                customer_pan=invoice_data.get("buyer_pan_number", ""),
            )
            customer.save()
            add_customer_book(customer)
        
        # Fetch selected bank
        bank_id = invoice_data.get("bank_id")
        bank = None
        if bank_id:
            try:
                bank = BankDetails.objects.get(id=bank_id)
            except BankDetails.DoesNotExist:
                bank = None  

        # Save product details
        update_products_from_invoice(invoice_data_processed, request)

        # Save invoice
        invoice_data_processed_json = json.dumps(invoice_data_processed)
        temp = json.loads(invoice_data_processed_json)


        new_invoice = Invoice(
            user=request.user,
            invoice_number=int(invoice_data["invoice-number"]),
            invoice_date=datetime.datetime.strptime(invoice_data["invoice-date"], "%Y-%m-%d"),
            bank=bank,
            invoice_customer=customer,
            invoice_json=invoice_data_processed_json,  # PO included in JSON
            invoice_customer_gst=invoice_data["customer-gst"],
            invoice_customer_phone=invoice_data["customer-phone"],
            invoice_amt_without_gst=temp["invoice_total_amt_without_gst"],
            invoice_amt_igst=temp["invoice_total_amt_igst"],
            invoice_amt_cgst=temp["invoice_total_amt_cgst"],
            invoice_amt_sgst=temp["invoice_total_amt_sgst"],
            invoice_amt_with_gst=temp["invoice_total_amt_with_gst"],
            business_tin_number=invoice_data.get("supplier_tin_number", ""),
            buyer_tin_number=invoice_data.get("buyer_tin_number", ""),
            terms_and_conditions=invoice_data.get("terms_and_conditions", ""),
            sup_pan_number=invoice_data.get("sup_pan_number", ""),
            project_description=invoice_data.get("project_description", ""),



        )
        
        new_invoice.save()
        print("Final Invoice Data:", new_invoice)

        # Update inventory and customer book
        update_inventory(new_invoice, request)
        auto_deduct_book_from_invoice(new_invoice)

        return redirect("invoice_viewer", invoice_id=new_invoice.id)

    return render(request, "gstbillingapp/invoice_create.html", context)



@login_required
def invoices(request):
    if request.user.is_superuser or request.user.is_staff:
        invoices_qs = Invoice.objects.all().order_by('-id')
    else:
        invoices_qs = Invoice.objects.filter(user=request.user).order_by('-id')

    context = {
        'invoices': invoices_qs
    }
    return render(request, 'gstbillingapp/invoices.html', context)


@login_required
def invoice_viewer(request, invoice_id):

    # If admin or staff -> can view ANY invoice
    if request.user.is_staff or request.user.is_superuser:
        invoice_obj = get_object_or_404(Invoice, id=invoice_id)
    else:
        # Normal user -> only their own invoices
        invoice_obj = get_object_or_404(Invoice, user=request.user, id=invoice_id)

    user_profile = get_object_or_404(UserProfile, user=request.user)

    invoice_json = json.loads(invoice_obj.invoice_json)

    # Ensure project_description is available even for older invoices
    if 'project_description' not in invoice_json and hasattr(invoice_obj, 'project_description'):
        invoice_json['project_description'] = invoice_obj.project_description

    context = {
        'invoice': invoice_obj,
        'invoice_data': invoice_json,
        'currency': "₹",
        'total_in_words': num2words.num2words(
            int(invoice_json['invoice_total_amt_with_gst']),
            lang='en_IN'
        ).title(),
        'user_profile': user_profile,
        'bank_details': invoice_obj.bank,
        'sup_pan_number': getattr(invoice_obj, 'sup_pan_number', None),
    }

    return render(request, 'gstbillingapp/invoice_printer.html', context)


@login_required
def invoice_delete(request):
    if request.method == "POST":
        invoice_id = request.POST["invoice_id"]
        print(invoice_id)
        invoice_obj = get_object_or_404(Invoice, user=request.user, id=invoice_id)
        if len(request.POST.getlist('inventory-del')):
            remove_inventory_entries_for_invoice(invoice_obj, request.user)
        invoice_obj.delete()
    return redirect('invoices')

@login_required
def customers(request):
    context = {}

    if request.user.is_staff or request.user.is_superuser:
        # Admin can see all customers
        customers_qs = Customer.objects.all()
    else:
        # Normal user can see only their customers
        customers_qs = Customer.objects.filter(user=request.user)

    context['customers'] = customers_qs
    return render(request, 'gstbillingapp/customers.html', context)


@login_required
def products(request):
    context = {}

    if request.user.is_staff or request.user.is_superuser:
        # Admin can see all products
        products_qs = Product.objects.all()
    else:
        # Normal user can see only their products
        products_qs = Product.objects.filter(user=request.user)

    context['products'] = products_qs
    return render(request, 'gstbillingapp/products.html', context)


@login_required
def customersjson(request):
    customers = list(Customer.objects.filter(user=request.user).values(
        'customer_name',
        'customer_address',
        'customer_phone',
        'customer_gst',
        'customer_pan',  
    ))
    return JsonResponse(customers, safe=False)


@login_required
def productsjson(request):
    products = list(Product.objects.filter(user=request.user).values())
    return JsonResponse(products, safe=False)


@login_required
def customer_edit(request, customer_id):
    customer_obj = get_object_or_404(Customer, user=request.user, id=customer_id)
    if request.method == "POST":
        customer_form = CustomerForm(request.POST, instance=customer_obj)
        if customer_form.is_valid():
            new_customer = customer_form.save()
            return redirect('customers')
    context = {}
    context['customer_form'] = CustomerForm(instance=customer_obj)
    return render(request, 'gstbillingapp/customer_edit.html', context)


@login_required
def customer_delete(request):
    if request.method == "POST":
        customer_id = request.POST["customer_id"]
        customer_obj = get_object_or_404(Customer, user=request.user, id=customer_id)
        customer_obj.delete()
    return redirect('customers')


@login_required
def customer_add(request):
    if request.method == "POST":
        customer_form = CustomerForm(request.POST)
        new_customer = customer_form.save(commit=False)
        new_customer.user = request.user
        new_customer.save()
        # create customer book
        add_customer_book(new_customer)
        return redirect('customers')
    context = {}
    context['customer_form'] = CustomerForm()
    return render(request, 'gstbillingapp/customer_edit.html', context)


@login_required
def product_edit(request, product_id):
    product_obj = get_object_or_404(Product, user=request.user, id=product_id)
    if request.method == "POST":
        product_form = ProductForm(request.POST, instance=product_obj)
        if product_form.is_valid():
            new_product = product_form.save()
            return redirect('products')
    context = {}
    context['product_form'] = ProductForm(instance=product_obj)
    return render(request, 'gstbillingapp/product_edit.html', context)


@login_required
def product_add(request):
    if request.method == "POST":
        product_form = ProductForm(request.POST)
        if product_form.is_valid():
            new_product = product_form.save(commit=False)
            new_product.user = request.user
            new_product.save()
            create_inventory(new_product)

            return redirect('products')
    context = {}
    context['product_form'] = ProductForm()
    return render(request, 'gstbillingapp/product_edit.html', context)


@login_required
def product_delete(request):
    if request.method == "POST":
        product_id = request.POST["product_id"]
        product_obj = get_object_or_404(Product, user=request.user, id=product_id)
        product_obj.delete()
    return redirect('products')



# ================= Inventory Views ===========================
@login_required
def inventory(request):
    context = {}
    context['inventory_list'] = Inventory.objects.filter(user=request.user)
    context['untracked_products'] = Product.objects.filter(user=request.user, inventory=None)
    return render(request, 'gstbillingapp/inventory.html', context)

@login_required
def inventory_logs(request, inventory_id):
    context = {}
    inventory = get_object_or_404(Inventory, id=inventory_id, user=request.user)
    inventory_logs = InventoryLog.objects.filter(user=request.user, product=inventory.product).order_by('-id')
    context['inventory'] = inventory
    context['inventory_logs'] = inventory_logs
    return render(request, 'gstbillingapp/inventory_logs.html', context)


@login_required
def inventory_logs_add(request, inventory_id):
    context = {}
    inventory = get_object_or_404(Inventory, id=inventory_id, user=request.user)
    inventory_logs = Inventory.objects.filter(user=request.user, product=inventory.product)
    context['inventory'] = inventory
    context['inventory_logs'] = inventory_logs
    context['form'] = InventoryLogForm()

    if request.method == "POST":
        inventory_log_form = InventoryLogForm(request.POST)
        invoice_no = request.POST["invoice_no"]
        invoice = None
        if invoice_no:
            try:
                invoice_no = int(invoice_no)
                invoice = Invoice.objects.get(user=request.user, invoice_number=invoice_no)
            except:
                context['error_message'] = "Incorrect invoice number %s"%(invoice_no,)
                return render(request, 'gstbillingapp/inventory_logs_add.html', context)
                context['form'] = inventory_log_form
                return render(request, 'gstbillingapp/inventory_logs_add.html', context)


        inventory_log = inventory_log_form.save(commit=False)
        inventory_log.user = request.user
        inventory_log.product = inventory.product
        if invoice:
            inventory_log.associated_invoice = invoice
        inventory_log.save()
        inventory.current_stock = inventory.current_stock + inventory_log.change
        inventory.last_log = inventory_log
        inventory.save()
        return redirect('inventory_logs', inventory.id)

    
    return render(request, 'gstbillingapp/inventory_logs_add.html', context)

# ===================== Book views =============================

@login_required
def books(request):
    context = {}
    context['book_list'] = Book.objects.filter(user=request.user)
    return render(request, 'gstbillingapp/books.html', context)


@login_required
def book_logs(request, book_id):
    context = {}
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book_logs = BookLog.objects.filter(parent_book=book).order_by('-id')
    context['book'] = book
    context['book_logs'] = book_logs
    return render(request, 'gstbillingapp/book_logs.html', context)


@login_required
def book_logs_add(request, book_id):
    context = {}
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book_logs = BookLog.objects.filter(parent_book=book)
    context['book'] = book
    context['book_logs'] = book_logs
    context['form'] = BookLogForm()

    if request.method == "POST":
        book_log_form = BookLogForm(request.POST)
        invoice_no = request.POST["invoice_no"]
        invoice = None
        if invoice_no:
            try:
                invoice_no = int(invoice_no)
                invoice = Invoice.objects.get(user=request.user, invoice_number=invoice_no)
            except:
                context['error_message'] = "Incorrect invoice number %s"%(invoice_no,)
                return render(request, 'gstbillingapp/book_logs_add.html', context)
                context['form'] = book_log_form
                return render(request, 'gstbillingapp/book_logs_add.html', context)


        book_log = book_log_form.save(commit=False)
        book_log.parent_book = book
        if invoice:
            book_log.associated_invoice = invoice
        book_log.save()

        book.current_balance = book.current_balance + book_log.change
        book.last_log = book_log
        book.save()
        return redirect('book_logs', book.id)

    return render(request, 'gstbillingapp/book_logs_add.html', context)



# ================= Static Pages ==============================
@login_required 
def landing_page(request):
    context = {}
    return render(request, 'gstbillingapp/pages/landing_page.html', context)


##########add bank ########
from django.shortcuts import render, redirect
from .models import BankDetails
from django.contrib import messages

def add_bank(request):
    if request.method == "POST":
        bank_name = request.POST.get("bankname")
        account_holder_name = request.POST.get("acc_holder_name")
        account_number = request.POST.get("account_number")
        ifsc_code = request.POST.get("ifcs_code")
        branch_name = request.POST.get("branch_name")
        address = request.POST.get("address")
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email_b")


        bank_details = BankDetails(
            bank_name=bank_name,
            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            branch_name=branch_name,
            address=address,
            phone_number=phone_number,
            email=email
        )
        bank_details.save()
        
        messages.success(request, "Bank details added successfully!")
        return redirect("invoices")  

    return render(request, "gstbillingapp/add_bank.html")


def display_bank(request):
    banks=BankDetails.objects.all()

    return render(request,'gstbillingapp/display_bank.html',{'banks':banks})

#### to fetch po #########

import json
import logging
from django.http import JsonResponse
from .models import Customer, Invoice

# Configure logging
logger = logging.getLogger(__name__)

def get_all_vehicle_numbers_by_name(request):
    customer_name = request.GET.get("customer_name", "").strip()

    if not customer_name:
        return JsonResponse({"error": "Customer name is required"}, status=400)

    try:
        # Find the customer by name
        customer = Customer.objects.filter(customer_name__iexact=customer_name).first()

        if customer:
            # Fetch all invoices related to this customer, ordered by latest date
            invoices = Invoice.objects.filter(invoice_customer=customer).order_by('-invoice_date')

            vehicle_numbers = []

            for invoice in invoices:
                if invoice.invoice_json:
                    invoice_data = json.loads(invoice.invoice_json)
                    vehicle_number = invoice_data.get("vehicle_number", "")  # Extract vehicle number

                    if vehicle_number and vehicle_number not in vehicle_numbers:
                        vehicle_numbers.append(vehicle_number)  # Add unique vehicle numbers
            
            # **Print and log vehicle numbers for debugging**
            print(f"Fetched Vehicle Numbers for {customer_name}: {vehicle_numbers}")
            logger.info(f"Fetched Vehicle Numbers for {customer_name}: {vehicle_numbers}")

            return JsonResponse({"vehicle_numbers": vehicle_numbers, "debug": f"Fetched: {vehicle_numbers}"})  # Return all vehicle numbers

        else:
            return JsonResponse({"vehicle_numbers": [], "debug": "No customer found"})  # No customer found

    except Exception as e:
        print(f"Error fetching vehicle numbers: {str(e)}")
        logger.error(f"Error fetching vehicle numbers: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def invoice_edit(request, invoice_id):

    invoice = get_object_or_404(Invoice, id=invoice_id)

    # non-admin can edit only own invoice
    if not request.user.is_superuser and invoice.user != request.user:
        return HttpResponseForbidden("Not allowed")

    banks = BankDetails.objects.all()

    # Load stored JSON
    existing_data = json.loads(invoice.invoice_json)
    
    # Ensure project_description is available even for older invoices
    if 'project_description' not in existing_data and hasattr(invoice, 'project_description'):
        existing_data['project_description'] = invoice.project_description

    if request.method == "POST":

        # rollback old inventory & book entries
        remove_inventory_entries_for_invoice(invoice, invoice.user)

        invoice_data_processed = invoice_data_processor(request.POST)

        update_products_from_invoice(invoice_data_processed, request)

        invoice.invoice_json = json.dumps(invoice_data_processed)

        temp = invoice_data_processed

        invoice.invoice_number = int(request.POST["invoice-number"])
        invoice.invoice_date = request.POST["invoice-date"]
        invoice.invoice_amt_without_gst = temp["invoice_total_amt_without_gst"]
        invoice.invoice_amt_igst = temp["invoice_total_amt_igst"]
        invoice.invoice_amt_cgst = temp["invoice_total_amt_cgst"]
        invoice.invoice_amt_sgst = temp["invoice_total_amt_sgst"]
        invoice.invoice_amt_with_gst = temp["invoice_total_amt_with_gst"]
        bank_id = request.POST.get("bank_id")
        if bank_id:
            invoice.bank = BankDetails.objects.get(id=bank_id)

        invoice.project_description = request.POST.get("project_description", "")

        invoice.save()

        # re-apply inventory & book effect
        update_inventory(invoice, request)
        auto_deduct_book_from_invoice(invoice)

        return redirect("invoice_viewer", invoice_id=invoice.id)

    context = {
        "invoice": invoice,
        "banks": banks,
        "invoice_data": existing_data,
    }

    return render(request, "gstbillingapp/invoice_edit.html", context)

from .models import CreditNote

@login_required
def credit_note_create(request):
    banks = BankDetails.objects.all()
    invoices_list = Invoice.objects.filter(user=request.user).order_by('-id')

    today = date.today()
    inyear = today.strftime("%y")
    inmonth = today.strftime("%m")

    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not user_profile.business_title:
        from django.contrib import messages
        messages.error(request, "Please update your business title in your profile.")
        return redirect('user_profile')

    context = {
        "banks": banks,
        "invoices_list": invoices_list,
        "default_invoice_number": CreditNote.objects.filter(user=request.user).aggregate(Max('credit_note_number'))['credit_note_number__max'],
        "default_invoice_date": datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d'),
    }

    if not context["default_invoice_number"]:
        invno = str(inyear) + str(inmonth) + str("001")
        context["default_invoice_number"] = invno
    else:
        temp = str(context["default_invoice_number"])
        if inyear != temp[:2] or inmonth != temp[2:4]:
            invno = str(inyear) + str(inmonth)
        else:
            context["default_invoice_number"] += 1

    if request.method == "POST":
        invoice_data = request.POST

        validation_error = invoice_data_validator(invoice_data)
        if validation_error:
            context["error_message"] = validation_error
            return render(request, "gstbillingapp/credit_note_create.html", context)

        invoice_data_processed = invoice_data_processor(invoice_data)

        customer = Customer.objects.filter(
            user=request.user,
            customer_name=invoice_data["customer-name"],
            customer_address=invoice_data["customer-address"],
            customer_phone=invoice_data["customer-phone"],
            customer_gst=invoice_data["customer-gst"],
            customer_pan=invoice_data.get("buyer_pan_number", "")
        ).first()

        if not customer:
            customer = Customer(
                user=request.user,
                customer_name=invoice_data["customer-name"],
                customer_address=invoice_data["customer-address"],
                customer_phone=invoice_data["customer-phone"],
                customer_gst=invoice_data["customer-gst"],
                customer_pan=invoice_data.get("buyer_pan_number", ""),
            )
            customer.save()

        bank_id = invoice_data.get("bank_id")
        bank = None
        if bank_id:
            try:
                bank = BankDetails.objects.get(id=bank_id)
            except BankDetails.DoesNotExist:
                bank = None  

        associated_invoice_id = invoice_data.get("associated_invoice_id")
        associated_invoice = None
        if associated_invoice_id:
            try:
                associated_invoice = Invoice.objects.get(id=associated_invoice_id, user=request.user)
            except Invoice.DoesNotExist:
                pass

        update_products_from_invoice(invoice_data_processed, request)

        invoice_data_processed_json = json.dumps(invoice_data_processed)
        temp = json.loads(invoice_data_processed_json)

        new_cn = CreditNote(
            user=request.user,
            credit_note_number=int(invoice_data["invoice-number"]), 
            credit_note_date=datetime.datetime.strptime(invoice_data["invoice-date"], "%Y-%m-%d"),
            associated_invoice=associated_invoice,
            bank=bank,
            credit_note_customer=customer,
            credit_note_json=invoice_data_processed_json,
            credit_note_customer_gst=invoice_data["customer-gst"],
            credit_note_customer_phone=invoice_data["customer-phone"],
            credit_note_amt_without_gst=temp["invoice_total_amt_without_gst"],
            credit_note_amt_igst=temp["invoice_total_amt_igst"],
            credit_note_amt_cgst=temp["invoice_total_amt_cgst"],
            credit_note_amt_sgst=temp["invoice_total_amt_sgst"],
            credit_note_amt_with_gst=temp["invoice_total_amt_with_gst"],
            business_tin_number=invoice_data.get("supplier_tin_number", ""),
            buyer_tin_number=invoice_data.get("buyer_tin_number", ""),
            terms_and_conditions=invoice_data.get("terms_and_conditions", ""),
            sup_pan_number=invoice_data.get("sup_pan_number", ""),
            project_description=invoice_data.get("project_description", ""),
        )
        
        new_cn.save()

        return redirect("credit_note_viewer", credit_note_id=new_cn.id)

    return render(request, "gstbillingapp/credit_note_create.html", context)

@login_required
def credit_notes(request):
    if request.user.is_superuser or request.user.is_staff:
        cn_qs = CreditNote.objects.all().order_by('-id')
    else:
        cn_qs = CreditNote.objects.filter(user=request.user).order_by('-id')

    context = {
        "credit_notes": cn_qs
    }
    return render(request, "gstbillingapp/credit_notes.html", context)

@login_required
def credit_note_viewer(request, credit_note_id):
    if request.user.is_staff or request.user.is_superuser:
        cn_obj = get_object_or_404(CreditNote, id=credit_note_id)
    else:
        cn_obj = get_object_or_404(CreditNote, user=request.user, id=credit_note_id)

    user_profile = get_object_or_404(UserProfile, user=request.user)
    cn_json = json.loads(cn_obj.credit_note_json)

    if "project_description" not in cn_json and hasattr(cn_obj, "project_description"):
        cn_json["project_description"] = cn_obj.project_description

    context = {
        "invoice": cn_obj, 
        "credit_note": cn_obj,
        "invoice_data": cn_json,
        "currency": "₹",
        "total_in_words": num2words.num2words(
            int(cn_json["invoice_total_amt_with_gst"]),
            lang="en_IN"
        ).title(),
        "user_profile": user_profile,
        "bank_details": cn_obj.bank,
        "sup_pan_number": getattr(cn_obj, "sup_pan_number", None),
    }

    return render(request, "gstbillingapp/credit_note_printer.html", context)

@login_required
def credit_note_delete(request):
    if request.method == "POST":
        cn_id = request.POST["invoice_id"]
        cn_obj = get_object_or_404(CreditNote, user=request.user, id=cn_id)
        cn_obj.delete()
    return redirect("credit_notes")

@login_required
def credit_note_edit(request, credit_note_id):
    cn = get_object_or_404(CreditNote, id=credit_note_id)

    if not request.user.is_superuser and cn.user != request.user:
        return HttpResponseForbidden("Not allowed")

    banks = BankDetails.objects.all()
    invoices_list = Invoice.objects.filter(user=request.user).order_by("-id")

    existing_data = json.loads(cn.credit_note_json)
    
    if "project_description" not in existing_data and hasattr(cn, "project_description"):
        existing_data["project_description"] = cn.project_description

    if request.method == "POST":
        invoice_data_processed = invoice_data_processor(request.POST)

        update_products_from_invoice(invoice_data_processed, request)

        cn.credit_note_json = json.dumps(invoice_data_processed)

        temp = invoice_data_processed

        cn.credit_note_number = int(request.POST["invoice-number"])
        cn.credit_note_date = request.POST["invoice-date"]
        cn.credit_note_amt_without_gst = temp["invoice_total_amt_without_gst"]
        cn.credit_note_amt_igst = temp["invoice_total_amt_igst"]
        cn.credit_note_amt_cgst = temp["invoice_total_amt_cgst"]
        cn.credit_note_amt_sgst = temp["invoice_total_amt_sgst"]
        cn.credit_note_amt_with_gst = temp["invoice_total_amt_with_gst"]
        
        bank_id = request.POST.get("bank_id")
        if bank_id:
            cn.bank = BankDetails.objects.get(id=bank_id)

        associated_invoice_id = request.POST.get("associated_invoice_id")
        if associated_invoice_id:
            try:
                cn.associated_invoice = Invoice.objects.get(id=associated_invoice_id, user=request.user)
            except Invoice.DoesNotExist:
                cn.associated_invoice = None
        else:
            cn.associated_invoice = None

        cn.project_description = request.POST.get("project_description", "")

        cn.save()

        return redirect("credit_note_viewer", credit_note_id=cn.id)

    context = {
        "invoice": cn,
        "credit_note": cn,
        "banks": banks,
        "invoices_list": invoices_list,
        "invoice_data": existing_data,
    }

    return render(request, "gstbillingapp/credit_note_edit.html", context)
