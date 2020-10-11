import dataclasses
import logging
import xml.etree.ElementTree as XmlParser
from saleor.order.models import Order
from saleor.product.models import Product, ProductVariant
from .danea_dataclass import DaneaProduct, DaneaVariant
from .product_manager import Utils
from .tasks import generate_product_task, update_product_task
from ..models import DaneaOrder

logger = logging.getLogger(__name__)


def process_product_xml(path) -> []:
    tree = XmlParser.parse(path)
    root = tree.getroot()
    warehouse = root.attrib.get('Warehouse')
    discarted_products = []
    for child in root.iter('Product'):
        product = DaneaProduct()
        product.original_name = child.find('Description').text
        product.name = child.find('Description').text.replace('\n', '')
        logger.info('Parsing product: ' + product.name)
        product.type = Utils.parse_type(product.name)
        if product.type is None:
            product.name = product.name + "(ERROR: PRODUCT TYPE)"
            logger.error('Unable to find type for')

        product.category = Utils.parse_category(product.name)
        if product.category is None:
            product.name = product.name + "(ERROR: CATEGORY)"
            logger.error('Unable to find category for')

        product.rm_code = Utils.extract_rm_code(product.name)
        if product.rm_code is None:
            product.name = product.name + "(ERROR: RMCODE)"
            logger.error('Unable to get rm code')

        product.original_color = child.find('Variants').find('Variant').find(
            'Color').text
        product.color = Utils.parse_color(product.original_color)
        if product.color is None:
            product.name = product.name + "(ERROR: PRODUCT COLOR)"
            logger.error('Unable to parse color')

        product.material = Utils.parse_material(product.name)
        if product.material is None:
            product.material = 'None'
        product.collection = Utils.parse_collection(product.name)
        if product.collection is None:
            product.collection = 'None'
        if product.type is not None \
                and product.category is not None \
                and product.rm_code is not None \
                and product.color is not None:
            product.name = Utils.clean_name(product.name)
            product.code = child.find('Code').text
            product.internal_id = child.find('InternalID').text
            product.gross_price = child.find('GrossPrice1').text
            product.net_price = child.find('NetPrice1').text

            try:
                product.sale_price = child.find('GrossPrice2').text
            except:
                product.sale_price = 0
            try:
                product.r120_price = child.find('GrossPrice3').text
            except:
                product.r120_price = 0
            try:
                product.r110_price = child.find('GrossPrice4').text
            except:
                product.r110_price = 0
            try:
                product.r100_price = child.find('GrossPrice5').text
            except:
                product.r100_price = 0
            try:
                product.web_price = child.find('GrossPrice6').text
            except:
                product.web_price = 0
            try:
                product.rm_collection = child.find('CustomField3').text
            except:
                product.rm_collection = 'None'
            product.variants = []
            for variant in child.find('Variants').iter('Variant'):
                danea_variant = DaneaVariant()
                danea_variant.barcode = variant.find('Barcode').text
                danea_variant.qty = variant.find('AvailableQty').text
                danea_variant.size = variant.find('Size').text
                product.variants.append(danea_variant)
            logger.info('Product successfully parsed.')
            if Product.objects.filter(slug=product.code).exists():
                # Async celery task
                product = dataclasses.asdict(product)
                update_product_task.delay(product, warehouse)
            else:
                # Async celery task
                product = dataclasses.asdict(product)
                generate_product_task.delay(product, warehouse)
        else:
            discarted_products.append(product.name)
            logger.error('Error parsing product, product has been discarted.')
    return discarted_products


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
    document.find('CustomerPostcode').text = order.shipping_address.postal_code
    document.find('CustomerEmail').text = order.get_customer_email()
    document.find('CustomerAddress').text = order.shipping_address.street_address_1
    document.find('CustomerCity').text = order.shipping_address.city
    document.find('CustomerProvince').text = order.shipping_address.country_area
    document.find('CustomerCountry').text = order.shipping_address.country.__str__()
    document.find('PaymentName').text = 'PayPal'
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
    # TODO Figure out a way to calculate discounts based on each single product
    rows = []
    for order_line in order.lines.all():
        row = create_row()
        variant = ProductVariant.objects.get(sku=order_line.product_sku)
        row.find('Description').text = variant.product.private_metadata.get(
            'original_name')
        row.find('Code').text = variant.product.slug
        price = variant.product.price.amount * order_line.quantity
        row.find('Price').text = price.__str__()
        discount_amout = variant.product.price.amount * order_line.quantity - order_line.get_total().gross.amount
        discount_percentage = 100 * discount_amout / price
        row.find('Discounts').text = discount_percentage.__str__()
        row.find('Color').text = variant.product.private_metadata.get('original_color')
        row.find('Size').text = variant.private_metadata.get('original_size')
        row.find('Qty').text = order_line.quantity.__str__()
        row.find('Um').text = 'pz'
        row.find('Stock').text = 'true'
        row.find('VatCode').text = '22'
        rows.append(row)
    document.find('Rows').extend(rows)
    payments = []
    for payment in order.payments.all():
        pay = create_payment()
        pay.find('Advance').text = 'false'
        pay.find('Date').text = payment.created.strftime("%Y-%m-%d")
        pay.find('Amount').text = payment.get_captured_amount().amount.__str__()
        pay.find('Paid').text = 'true'
    document.find('Payments').extend(payments)

    return document


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
