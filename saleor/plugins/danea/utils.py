import dataclasses
import decimal
import logging
import xml.etree.ElementTree as XmlParser
from saleor.product.models import Product, ProductVariant, AttributeValue
from .danea_dataclass import DaneaProduct, DaneaVariant
from .tasks import generate_product_task, update_product_task, \
    update_available_products_task, update_google_feeds_task
from ..models import DaneaOrder, DaneaCategoryMappings, DaneaAttributeValuesMappings
from ...order.models import Order
from ...payment.models import Payment
from ...warehouse.models import Warehouse

logger = logging.getLogger(__name__)


def process_product_xml(path) -> []:
    tree = XmlParser.parse(path)
    root = tree.getroot()
    warehouse = root.attrib.get('Warehouse')
    discarted_products = []
    danea_product_slugs = []
    if not validate_warehouse(warehouse):
        return discarted_products.append('Invalid Warehouse =' + warehouse)
    for child in root.iter('Product'):
        product = extract_product(child)
        if check_for_errors(product):
            product.name = clean_name(product.name)
            extract_private_metadata(child, product)
            product.variants = []
            for variant in child.find('Variants').iter('Variant'):
                danea_variant = extract_variant(variant)
                if danea_variant.size is not None and danea_variant.original_size is not None:
                    product.variants.append(danea_variant)
                else:
                    discarted_products.append(product.name + "(ERROR: VARIANT SIZE)")
            if len(product.variants) <= 4:
                if Product.objects.filter(slug=product.code).exists():
                    danea_product_slugs.append(product.code)
                    product = dataclasses.asdict(product)
                    update_product_task.delay(product, warehouse)
                else:
                    danea_product_slugs.append(product.code)
                    product = dataclasses.asdict(product)
                    generate_product_task.delay(product, warehouse)
            else:
                discarted_products.append(product.name + "(ERROR: VARIANT NR)")
        else:
            discarted_products.append(product.name)
    update_available_products_task.delay(danea_product_slugs)
    update_google_feeds_task.apply_async(countdown=800)
    return discarted_products


def extract_variant(variant):
    danea_variant = DaneaVariant()
    danea_variant.barcode = variant.find('Barcode').text
    danea_variant.qty = variant.find('AvailableQty').text
    danea_variant.size = parse_size(variant.find('Size').text)
    danea_variant.original_size = variant.find('Size').text
    return danea_variant


def parse_size(size: str):
    size = size.lower()
    if DaneaAttributeValuesMappings.objects.exists(danea_field=size,
                                                   attribute_type='size'):
        return DaneaAttributeValuesMappings.objects.get(
            danea_field=size
        ).saleor_attribute_value_slug
    else:
        return None


def extract_private_metadata(child, product):
    product.code = child.find('Code').text
    product.internal_id = child.find('InternalID').text
    product.gross_price = decimal.Decimal(child.find('GrossPrice1').text)
    product.net_price = decimal.Decimal(child.find('NetPrice1').text)
    try:
        product.sale_price = decimal.Decimal(child.find('GrossPrice2').text)
    except:
        product.sale_price = decimal.Decimal(0)
    try:
        product.r120_price = decimal.Decimal(child.find('GrossPrice3').text)
    except:
        product.r120_price = decimal.Decimal(0)
    try:
        product.r110_price = decimal.Decimal(child.find('GrossPrice4').text)
    except:
        product.r110_price = decimal.Decimal(0)
    try:
        product.r100_price = decimal.Decimal(child.find('GrossPrice5').text)
    except:
        product.r100_price = decimal.Decimal(0)
    try:
        product.web_price = decimal.Decimal(child.find('GrossPrice6').text)
    except:
        product.web_price = decimal.Decimal(0)
    try:
        product.rm_collection = child.find("CustomField3").text
    except:
        product.rm_collection = None


def check_for_errors(product: DaneaProduct) -> bool:
    return product.type is not None and product.category is not None \
           and product.rm_code is not None and product.color is not None \
           and product.material is not None


def extract_product(child) -> DaneaProduct:
    product = DaneaProduct()
    extract_name(child, product)
    extract_type_and_category(child, product)
    extract_rm_code(child, product)
    extract_color(child, product)
    extract_material(child, product)
    return product


def extract_name(child, product):
    product.original_name = child.find('Description').text
    product.name = child.find('Description').text.replace('\n', '')


def extract_material(child, product):
    try:
        material = child.find("Subcategory").text
        attribute = AttributeValue.objects.get(slug=material.lower())
        product.material = attribute.slug
    except:
        product.material = None
        product.name = product.name + "(ERROR: PRODUCT MATERIAL)"


def extract_type_and_category(child, product: DaneaProduct):
    try:
        category = child.find('Category').text.strip().lower()
        mapping = DaneaCategoryMappings.objects.get(danea_field=category)
        product.type = mapping.saleor_type_slug.strip().lower()
        product.category = mapping.saleor_category_slug.strip().lower()
    except:
        product.type = None
        product.name = product.name + "(ERROR: PRODUCT TYPE/CATEGORY)"
        logger.error("Unable to parse type/category")


def extract_color(child, product: DaneaProduct):
    product.original_color = child.find('Variants').find('Variant').find(
        'Color').text
    color = product.original_color[:2].lower()
    if DaneaAttributeValuesMappings.objects.exists(danea_field=color):
        return DaneaAttributeValuesMappings.objects.get(
            danea_field=color[:2]
        ).saleor_attribute_value_slug
    else:
        product.name = product.name + "(ERROR: PRODUCT COLOR)"


def extract_rm_code(child, product: DaneaProduct):
    product.rm_code = get_rm_code_from_product_name(product.name)
    if product.rm_code is None:
        product.name = product.name + "(ERROR: RMCODE)"


def get_rm_code_from_product_name(product_name: str):
    index = product_name.find('(')
    code = ''
    if index > -1:
        index += 1
        while product_name[index] != ')':
            code += product_name[index]
            index += 1
    else:
        return None
    return code


def create_orders():
    file = generate_file()
    documents = []
    for order in DaneaOrder.objects.all():
        saleor_order = Order.objects.get(id=order.saleor_order_id)
        document = process_order(saleor_order)
        documents.append(document)
        order.delete()
    file.find('Documents').extend(documents)
    return file


def process_order(order: Order):
    document = create_document()
    document.find('CustomerName').text = order.shipping_address.full_name
    document.find('CustomerTel').text = order.shipping_address.phone.__str__()
    document.find('Number').text = order.id.__str__()
    document.find('Numbering').text = 'Web'
    document.find('CustomerPostcode').text = order.shipping_address.postal_code
    document.find('CustomerEmail').text = order.get_customer_email()
    document.find('CustomerAddress').text = order.shipping_address.street_address_1
    document.find('CustomerCity').text = order.shipping_address.city
    document.find('CustomerProvince').text = order.shipping_address.country_area
    document.find('CustomerCountry').text = order.shipping_address.country.__str__()
    document.find('PaymentName').text = extract_payment_method(
        order.get_last_payment().gateway.__str__())
    document.find('DocumentType').text = 'C'
    document.find(
        'Warehouse').text = '02 PRINCIPALE'  # TODO implemenort warehouse search
    document.find('Date').text = order.created.strftime("%Y-%m-%d")
    document.find('Total').text = order.total_gross_amount.__str__()
    document.find('PriceList').text = 'Pubblico'  # TODO implement pricelist
    document.find('PricesIncludeVat').text = 'true'
    document.find('SalesAgent').text = 'e-commerce'
    document.find('CostDescription').text = 'Spese di Spedizione'
    document.find('CostAmount').text = order.shipping_price.gross.amount.__str__()
    rows = []
    for order_line in order.lines.all():
        row = create_row()
        variant = ProductVariant.objects.get(sku=order_line.product_sku)
        row.find('Description').text = variant.product.private_metadata.get(
            'original_name')
        row.find('Code').text = variant.product.slug
        price = variant.price_amount * order_line.quantity
        row.find('Price').text = price.__str__()
        discount_amout = variant.price_amount * order_line.quantity - order_line.get_total().gross.amount
        discount_percentage = 100 * discount_amout / price
        row.find('Discounts').text = discount_percentage.__str__()
        row.find('Color').text = variant.product.private_metadata.get('original_color')
        row.find('Size').text = variant.private_metadata.get('original_size')
        row.find('Qty').text = order_line.quantity.__str__()
        row.find('Um').text = 'pz'
        row.find('Stock').text = 'true'
        row.find('VatCode').text = '22'
        rows.append(row)
    if order.voucher:
        row = create_row()
        row.find('Description').text = 'Voucher :' + order.voucher.code
        row.find('Price').text = str(order.voucher.discount_value * -1)
        row.find('Um').text = 'pz'
        row.find('Stock').text = 'true'
        row.find('Qty').text = '1'
        rows.append(row)
    document.find('Rows').extend(rows)
    payments = []
    pay = create_payment()
    payment: Payment = order.get_last_payment()
    pay.find('Advance').text = 'false'
    pay.find('Date').text = payment.created.strftime("%Y-%m-%d")
    if payment.charge_status.__str__() == 'fully-charged':
        pay.find('Amount').text = payment.get_captured_amount().amount.__str__()
        pay.find('Paid').text = 'true'
    if payment.charge_status.__str__() == 'not-charged':
        pay.find('Paid').text = 'false'
        pay.find('Amount').text = payment.get_authorized_amount().amount.__str__()
    payments.append(pay)
    document.find('Payments').extend(payments)

    return document


def extract_payment_method(gateway):
    if gateway == 'todajoia.payments.OnDeliveryPayment':
        return 'Contrassegno'
    if gateway == 'mirumee.payments.braintree':
        return 'Braintree'
    if gateway == 'mirumee.payments.stripe':
        return 'Stripe'


def generate_file():
    element = XmlParser.Element(
        'EasyfattDocuments',
        AppVersion="2",
        Creator="Danea Easyfatt Enterprise  2020.46c",
        CreatorUrl="http://www.danea.it/software/easyfatt",
    )
    XmlParser.SubElement(element, 'Documents')
    company = XmlParser.SubElement(element, 'Company')
    XmlParser.SubElement(company, 'Name').text = "TODA JOIA"
    XmlParser.SubElement(company, 'Address').text = "VIA PUNICO, 19"
    XmlParser.SubElement(company, 'Postcode').text = "00058"
    XmlParser.SubElement(company, 'City').text = "SANTA MARINELLA"
    XmlParser.SubElement(company, 'Province').text = "RM"
    XmlParser.SubElement(company, 'Country').text = "Italia"
    XmlParser.SubElement(company, 'FiscalCode').text = "SRSCNC70R68Z602E"
    XmlParser.SubElement(company, 'VatCode').text = "15038141006"
    XmlParser.SubElement(company, 'Tel').text = "0766 520200"
    XmlParser.SubElement(company, 'Email').text = "direzione@todajoia.it"
    XmlParser.SubElement(company, 'HomePage').text = "https://todajoia.com"
    return element


def create_document():
    document = XmlParser.Element('Document')
    XmlParser.SubElement(document, 'CustomerCode')
    XmlParser.SubElement(document, 'CustomerWebLogin')
    XmlParser.SubElement(document, 'CustomerName')
    XmlParser.SubElement(document, 'CustomerTel')
    XmlParser.SubElement(document, 'CustomerEmail')
    XmlParser.SubElement(document, 'CustomerAddress')
    XmlParser.SubElement(document, 'CustomerPostcode')
    XmlParser.SubElement(document, 'CustomerCity')
    XmlParser.SubElement(document, 'CustomerProvince')
    XmlParser.SubElement(document, 'CustomerCountry')
    XmlParser.SubElement(document, 'DocumentType')
    XmlParser.SubElement(document, 'Warehouse')
    XmlParser.SubElement(document, 'Date')
    XmlParser.SubElement(document, 'Number')
    XmlParser.SubElement(document, 'Numbering')
    XmlParser.SubElement(document, 'CostDescription')
    XmlParser.SubElement(document, 'CostVatCode')
    XmlParser.SubElement(document, 'CostAmount')
    XmlParser.SubElement(document, 'ContribDescription')
    XmlParser.SubElement(document, 'ContribPerc')
    XmlParser.SubElement(document, 'ContribSubjectToWithholdingTax')
    XmlParser.SubElement(document, 'ContribAmount')
    XmlParser.SubElement(document, 'ContribVatCode')
    XmlParser.SubElement(document, 'TotalWithoutTax')
    XmlParser.SubElement(document, 'VatAmount')
    XmlParser.SubElement(document, 'WithholdingTaxAmount')
    XmlParser.SubElement(document, 'WithholdingTaxAmountB')
    XmlParser.SubElement(document, 'WithholdingTaxNameB')
    XmlParser.SubElement(document, 'Total')
    XmlParser.SubElement(document, 'PriceList')
    XmlParser.SubElement(document, 'PricesIncludeVat')
    XmlParser.SubElement(document, 'TotalSubjectToWithholdingTax')
    XmlParser.SubElement(document, 'WithholdingTaxPerc')
    XmlParser.SubElement(document, 'WithholdingTaxPerc2')
    XmlParser.SubElement(document, 'PaymentName')
    XmlParser.SubElement(document, 'PaymentBank')
    XmlParser.SubElement(document, 'InternalComment')
    XmlParser.SubElement(document, 'CustomField1')
    XmlParser.SubElement(document, 'CustomField3')
    XmlParser.SubElement(document, 'CustomField4')
    XmlParser.SubElement(document, 'FootNotes')
    XmlParser.SubElement(document, 'SalesAgent')
    XmlParser.SubElement(document, 'Rows')
    XmlParser.SubElement(document, 'Payments')
    return document


def create_row():
    row = XmlParser.Element('Row')
    XmlParser.SubElement(row, 'Code')
    XmlParser.SubElement(row, 'Description')
    XmlParser.SubElement(row, 'Qty')
    XmlParser.SubElement(row, 'Um')
    XmlParser.SubElement(row, 'Size')
    XmlParser.SubElement(row, 'Color')
    XmlParser.SubElement(row, 'Price')
    XmlParser.SubElement(row, 'Discounts')
    XmlParser.SubElement(
        row,
        'VatCode',
        Perc="22",
        Class="Imponibile",
        Description="Aliquota 22%"
    )
    XmlParser.SubElement(row, 'Total')
    XmlParser.SubElement(row, 'Stock')
    XmlParser.SubElement(row, 'Notes')
    return row


def create_payment():
    row = XmlParser.Element('Payment')
    XmlParser.SubElement(row, 'Advance')
    XmlParser.SubElement(row, 'Date')
    XmlParser.SubElement(row, 'Amount')
    XmlParser.SubElement(row, 'Paid')
    return row


def clean_name(product: str) -> str:
    p = product
    product_name: str = ''
    index: int = 0
    end = p.find('(')
    if end > -1:
        while index < end:
            product_name += p[index]
            index += 1
        p = product_name
    else:
        logger.error('Not able to clean name :' + p)
    return p


def validate_warehouse(warehouse: str) -> bool:
    return Warehouse.objects.filter(slug=warehouse.lower()).exists
