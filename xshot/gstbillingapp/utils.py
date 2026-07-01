import datetime
import json

from django.db.models import Sum


from .models import Product
from .models import Inventory
from .models import InventoryLog
from .models import Book
from .models import BookLog


def invoice_data_validator(invoice_data):
    
    # Validate Invoice Info ----------

    # invoice-number
    try:
        invoice_number = int(invoice_data['invoice-number'])
    except:
        print("Error: Incorrect Invoice Number")
        return "Error: Incorrect Invoice Number"

    # invoice date
    try:
        date_text = invoice_data['invoice-date']
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except:
        print("Error: Incorrect Invoice Date")
        return "Error: Incorrect Invoice Date"

    # Validate Customer Data ---------

    # customer-name
    if len(invoice_data['customer-name']) < 1 or len(invoice_data['customer-name']) > 200:
        print("Error: Incorrect Customer Name")
        return "Error: Incorrect Customer Name"

    if len(invoice_data['customer-address']) > 600:
        print("Error: Incorrect Customer Address")
        return "Error: Incorrect Customer Address"

    if len(invoice_data['customer-phone']) > 14:
        print("Error: Incorrect Customer Phone")
        return "Error: Incorrect Customer Phone"
    if len(invoice_data['customer-gst']) != 15 and len(invoice_data['customer-gst']) != 0:
        print("Error: Incorrect Customer GST")
        return "Error: Incorrect Customer GST"
    return None


def invoice_data_processor(invoice_post_data):
    print(invoice_post_data)
    processed_invoice_data = {}

    # Invoice Details
    processed_invoice_data['invoice_number'] = invoice_post_data['invoice-number']
    processed_invoice_data['invoice_date'] = invoice_post_data['invoice-date']

    # Billing (Customer) Details
    processed_invoice_data['customer_name'] = invoice_post_data['customer-name']
    processed_invoice_data['customer_address'] = invoice_post_data['customer-address']
    processed_invoice_data['customer_phone'] = invoice_post_data['customer-phone']
    processed_invoice_data['customer_gst'] = invoice_post_data['customer-gst']
    processed_invoice_data['customer_pan'] = invoice_post_data['buyer_pan_number']

    # Shipping Details
    if 'same-as-billing-checkbox' in invoice_post_data:
        # If checkbox is checked, use billing info as shipping info
        processed_invoice_data['shipping_name'] = processed_invoice_data['customer_name']
        processed_invoice_data['shipping_address'] = processed_invoice_data['customer_address']
        processed_invoice_data['shipping_phone'] = processed_invoice_data['customer_phone']
        processed_invoice_data['shipping_gst'] = processed_invoice_data['customer_gst']
        processed_invoice_data['shipping_pan'] = processed_invoice_data['customer_pan']
        processed_invoice_data['shipping_tin_number'] = processed_invoice_data.get('buyer_tin_number', '')
    else:
        # If checkbox not checked, use separate shipping info
        processed_invoice_data['shipping_name'] = invoice_post_data.get('shipping-name', '')
        processed_invoice_data['shipping_address'] = invoice_post_data.get('shipping-address', '')
        processed_invoice_data['shipping_phone'] = invoice_post_data.get('shipping-phone', '')
        processed_invoice_data['shipping_gst'] = invoice_post_data.get('shipping-gst', '')
        processed_invoice_data['shipping_tin_number'] = invoice_post_data.get('shipping_tin_number', '')

    # Other Invoice Fields
#     processed_invoice_data['vehicle_number'] = (
#     invoice_post_data.get('vehicle-number') or
#     invoice_post_data.get('vehicle-number-dropdown') or
#     ''
# )
# --- PO Number handling (dropdown + manual) ---

    manual_po = invoice_post_data.get("vehicle-number")
    dropdown_po = invoice_post_data.get("vehicle-number-dropdown")

    processed_invoice_data["vehicle_number"] = (
        manual_po.strip()
        if manual_po and manual_po.strip()
        else (dropdown_po.strip() if dropdown_po else "")
    )
    processed_invoice_data['business_tin_number'] = invoice_post_data.get('supplier_tin_number', '')
    processed_invoice_data['buyer_tin_number'] = invoice_post_data.get('buyer_tin_number', '')
    processed_invoice_data['terms_and_conditions'] = invoice_post_data.get('terms_and_conditions', '')
    processed_invoice_data['sup_pan_number'] = invoice_post_data.get('sup_pan_number', '')
    processed_invoice_data['project_description'] = invoice_post_data.get('project_description', '')

    # IGST Checkbox
    processed_invoice_data['igstcheck'] = 'igstcheck' in invoice_post_data

    # Totals
    processed_invoice_data['invoice_total_amt_without_gst'] = float(invoice_post_data['invoice-total-amt-without-gst'])
    processed_invoice_data['invoice_total_amt_sgst'] = float(invoice_post_data['invoice-total-amt-sgst'])
    processed_invoice_data['invoice_total_amt_cgst'] = float(invoice_post_data['invoice-total-amt-cgst'])
    processed_invoice_data['invoice_total_amt_igst'] = float(invoice_post_data['invoice-total-amt-igst'])
    processed_invoice_data['invoice_total_amt_with_gst'] = float(invoice_post_data['invoice-total-amt-with-gst'])

    # Line Items
    invoice_post_data = dict(invoice_post_data)
    processed_invoice_data['items'] = []

    for idx, product in enumerate(invoice_post_data['invoice-product']):
        if product:
            print(idx, product)
            item_entry = {
                'invoice_product': product,
                'invoice_hsn': invoice_post_data['invoice-hsn'][idx],
                'invoice_unit': invoice_post_data['invoice-unit'][idx],
                'invoice_qty': int(invoice_post_data['invoice-qty'][idx]),
                'invoice_rate_with_gst': float(invoice_post_data['invoice-rate-with-gst'][idx]),
                'invoice_gst_percentage': float(invoice_post_data['invoice-gst-percentage'][idx]),
                'invoice_rate_without_gst': float(invoice_post_data['invoice-rate-without-gst'][idx]),
                'invoice_amt_without_gst': float(invoice_post_data['invoice-amt-without-gst'][idx]),
                'invoice_amt_sgst': float(invoice_post_data['invoice-amt-sgst'][idx]),
                'invoice_amt_cgst': float(invoice_post_data['invoice-amt-cgst'][idx]),
                'invoice_amt_igst': float(invoice_post_data['invoice-amt-igst'][idx]),
                'invoice_amt_with_gst': float(invoice_post_data['invoice-amt-with-gst'][idx]),
            }
            processed_invoice_data['items'].append(item_entry)

    print(processed_invoice_data)
    return processed_invoice_data

# def update_products_from_invoice(invoice_data_processed, request):
#     for item in invoice_data_processed['items']:
#         new_product = False
#         if Product.objects.filter(user=request.user,
#                                   product_name=item['invoice_product'],
#                                   product_hsn=item['invoice_hsn'],
#                                   product_unit=item['invoice_unit'],
#                                   product_gst_percentage=item['invoice_gst_percentage']).exists():
#             product = Product.objects.get(user=request.user,
#                                           product_name=item['invoice_product'],
#                                           product_hsn=item['invoice_hsn'],
#                                           product_unit=item['invoice_unit'],
#                                           product_gst_percentage=item['invoice_gst_percentage'])
#         else:
#             new_product = True
#             product = Product(user=request.user,
#                               product_name=item['invoice_product'],
#                               product_hsn=item['invoice_hsn'],
#                               product_unit=item['invoice_unit'],
#                               product_gst_percentage=item['invoice_gst_percentage'])
#         product.product_rate_with_gst = item['invoice_rate_with_gst']
#         product.save()

#         if new_product:
#             create_inventory(product)

def update_products_from_invoice(invoice_data_processed, request):

    for item in invoice_data_processed['items']:

        if not Product.objects.filter(
            user=request.user,
            product_name=item['invoice_product'],
            product_hsn=item['invoice_hsn'],
            product_unit=item['invoice_unit'],
            product_gst_percentage=item['invoice_gst_percentage']
        ).exists():

            product = Product(
                user=request.user,
                product_name=item['invoice_product'],
                product_hsn=item['invoice_hsn'],
                product_unit=item['invoice_unit'],
                product_gst_percentage=item['invoice_gst_percentage'],
                product_rate_with_gst=item['invoice_rate_with_gst']
            )

            product.save()
            create_inventory(product)

            
#  ================== Inventory methods ====================

def create_inventory(product):
    if not Inventory.objects.filter(user=product.user, product=product).exists():
        new_inventory = Inventory(user=product.user, product=product)
        new_inventory.save()

def update_inventory(invoice, request):
    invoice_data =  json.loads(invoice.invoice_json)
    for item in invoice_data['items']:
        product = Product.objects.get(user=request.user,
                                      product_name=item['invoice_product'],
                                      product_hsn=item['invoice_hsn'],
                                      product_unit=item['invoice_unit'],
                                      product_gst_percentage=item['invoice_gst_percentage'])
        inventory = Inventory.objects.get(user=product.user, product=product)
        change = int(item['invoice_qty'])*(-1)
        inventory_log = InventoryLog(user=product.user,
                                     product=product,
                                     date=datetime.datetime.now(),
                                     change=change,
                                     change_type=4,
                                     associated_invoice=invoice,
                                     description="Sale - Auto Deduct")
        inventory_log.save()
        inventory.current_stock += change
        inventory.last_log = inventory_log
        inventory.save()


def remove_inventory_entries_for_invoice(invoice, user):
        inventory_logs = InventoryLog.objects.filter(user=user,
                                     associated_invoice=invoice)
        for inventory_log in inventory_logs:
            inventory_product = inventory_log.product
            inventory_log.delete()
            # update the inventory total
            inventory_obj = Inventory.objects.get(user=user, product=inventory_product)
            recalculate_inventory_total(inventory_obj, user)


def recalculate_inventory_total(inventory_obj, user):
    new_total = InventoryLog.objects.filter(user=user, product=inventory_obj.product).aggregate(Sum('change'))['change__sum']
    if not new_total:
        new_total = 0
    inventory_obj.current_stock = new_total
    inventory_obj.save()


# ================ Book methods ===========================

def add_customer_book(customer):
    # check if customer already exists
    if Book.objects.filter(user=customer.user, customer=customer).exists():
        return
    book = Book(user=customer.user,
                customer=customer)
    book.save()


def auto_deduct_book_from_invoice(invoice):
    invoice_data =  json.loads(invoice.invoice_json)

    book = Book.objects.get(user=invoice.user, customer=invoice.invoice_customer)

    book_log = BookLog(parent_book=book,
                       date=invoice.invoice_date,
                       change_type=1,
                       change=(-1.0)*float(invoice_data['invoice_total_amt_with_gst']),
                       associated_invoice=invoice,
                       description="Purchase - Auto Deduct")

    book_log.save()

    book.current_balance = book.current_balance + book_log.change
    book.last_log = book_log
    book.save()
