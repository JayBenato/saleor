import dataclasses
import logging
import xml.etree.ElementTree as XmlParser
from saleor.order.models import Order
from saleor.product.models import Product, ProductVariant, AttributeValue, Collection, \
    Category, ProductType
from .danea_dataclass import DaneaProduct, DaneaVariant
from .tasks import generate_product_task, update_product_task
from ..models import DaneaOrder, DaneaCategoryMappings
from ...warehouse.models import Warehouse

logger = logging.getLogger(__name__)


def process_product_xml(path) -> []:
    tree = XmlParser.parse(path)
    root = tree.getroot()
    warehouse = root.attrib.get('Warehouse')
    discarted_products = [str]
    if not validate_warehouse(warehouse):
        return discarted_products.append('Invalid Warehouse =' + warehouse)
    for child in root.iter('Product'):
        product = extract_product(child)
        if check_for_errors(product):
            product.name = clean_name(product.name)
            extract_private_metadata(child, product)
            product.variants = []
            for variant in child.find('Variants').iter('Variant'):
                danea_variant = DaneaVariant()
                extract_variant(danea_variant, variant)
                product.variants.append(danea_variant)
            if len(product.variants) <= 4:
                if Product.objects.filter(slug=product.code).exists():
                    product = dataclasses.asdict(product)
                    update_product_task.delay(product, warehouse)
                else:
                    product = dataclasses.asdict(product)
                    generate_product_task.delay(product, warehouse)
            else:
                discarted_products.append(product.name + "(ERROR: VARIANT NR)")
        else:
            discarted_products.append(product.name)
    return discarted_products


def extract_variant(danea_variant, variant):
    danea_variant.barcode = variant.find('Barcode').text
    danea_variant.qty = variant.find('AvailableQty').text
    danea_variant.size = parse_size(variant.find('Size').text)


def parse_size(size: str) -> str:
    size = size.lower()
    if size == 's' or size == 'p':
        return 's'
    elif size == 'm':
        return 'm'
    elif size == 'l' or size == 'g':
        return 'l'
    else:
        return 'xl'


def extract_private_metadata(child, product):
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


def check_for_errors(product: DaneaProduct) -> bool:
    return product.type is not None and product.category is not None \
           and product.rm_code is not None and product.color is not None \
           and product.material is not None


def extract_product(child) -> DaneaProduct:
    product = DaneaProduct()
    product.original_name = child.find('Description').text
    product.name = child.find('Description').text.replace('\n', '')
    logger.info('Parsing product: ' + product.name)
    extract_type_and_category(child, product)
    extract_rm_code(child, product)
    extract_color(child, product)
    extract_material(child, product)
    extract_collection(child, product)
    return product


def extract_material(child, product):
    try:
        material = child.find("Subcategory").text.lower()
        attribute = AttributeValue.objects.get(slug=material)
        product.material = attribute.slug
    except:
        product.material = None
        product.name = product.name + "(ERROR: PRODUCT MATERIAL)"
        logger.error("Unable to parse material")


def extract_collection(child, product):
    try:
        product.collection = child.find('WarehouseLocation').text.lower()
        if not Collection.objects.filter(slug=product.collection).exists():
            product.collection = parse_collection(product.name)

    except:
        product.collection = 'N'


def parse_collection(product_name: str):
    product_name = product_name.lower()
    if 'reverse' in product_name or 'double' in product_name:
        return 'reverse'
    if 'jeans' in product_name:
        return 'fake-jeans'
    logger.error("Unable to parse collection")
    return 'N'


def extract_type_and_category(child, product):
    try:
        category = child.find('Category').text
        logger.info("Parsing category :" + category)
        if category is not None:
            mapping = DaneaCategoryMappings.objects.get(danea_field=category.lower())
            if Category.objects.filter(slug=mapping.saleor_category_slug).exists() and \
                    ProductType.objects.filter(slug=mapping.saleor_type_slug).exists():
                product.type = mapping.saleor_type_slug
                product.category = mapping.saleor_category_slug
            else:
                product.type = None
                product.name = product.name + "(ERROR: PRODUCT TYPE/CATEGORY)"
                logger.error("Unable to find type/category")
    except:
        product.type = None
        product.name = product.name + "(ERROR: PRODUCT TYPE/CATEGORY)"
        logger.error("Unable to parse type/category")


def extract_color(child, product):
    product.original_color = child.find('Variants').find('Variant').find(
        'Color').text
    product.color = parse_color(product.original_color)
    if product.color is None:
        product.name = product.name + "(ERROR: PRODUCT COLOR)"
        logger.error("Unable to parse color")


def parse_color(color: str):
    color = color.lower()
    if 'dg' in color or 'sb' in color or 'es' in color:
        return 'multicolor'
    elif color.startswith('pt') or color.startswith('01'):
        return 'black'
    elif color.startswith('vm'):
        return 'red'
    elif color.startswith('vd'):
        return 'green'
    elif color.startswith('az'):
        return 'blue'
    elif color.startswith('lj'):
        return 'orange'
    elif color.startswith('bc'):
        return 'white'
    elif color.startswith('rs'):
        return 'pink'
    elif color.startswith('bd') or color.startswith('rx'):
        return 'bordeaux'
    elif color.startswith('me') or color.startswith('cz'):
        return 'grey'
    elif color.startswith('mr'):
        return 'brown'
    elif color.startswith('am'):
        return 'yellow'
    else:
        return None


def extract_rm_code(child, product):
    product.rm_code = parse_code(product.name)
    if product.rm_code is None:
        product.name = product.name + "(ERROR: RMCODE)"
    product.original_color = child.find('Variants').find('Variant').find(
        'Color').text


def parse_code(product_name: str):
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
