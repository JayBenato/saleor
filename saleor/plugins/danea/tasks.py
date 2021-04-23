import decimal
from ...data_feeds.google_merchant import update_feed
from .danea_dataclass import DaneaProduct, DaneaVariant
from .product_manager import generate_product, update_product
from ...celeryconf import app
from ...product.models import Product


@app.task
def generate_product_task(product, warehouse):
    product = to_danea_product(product)
    generate_product(product, warehouse)


@app.task
def update_product_task(product, warehouse):
    product = to_danea_product(product)
    update_product(product, warehouse)


@app.task
def update_available_products_task(product_slugs):
    for product in Product.objects.all():
        active_product = False
        for slug in product_slugs:
            if product.slug == slug:
                active_product = True
                break
        if active_product is False:
            product.is_published = False
            product.visible_in_listings = False
            product.available_for_purchase = None
            product.save()


@app.task
def update_google_feeds_task():
    update_feed()

def to_danea_product(dictionary) -> DaneaProduct:
    product = DaneaProduct()
    product.name = dictionary.get('name')
    product.original_name = dictionary.get('original_name')
    product.original_color = dictionary.get('original_color')
    product.code = dictionary.get('code')
    product.material = dictionary.get('material')
    product.type = dictionary.get('type')
    product.rm_code = dictionary.get('rm_code')
    product.collection = dictionary.get('collection')
    product.internal_id = dictionary.get('internal_id')
    product.net_price = decimal.Decimal(dictionary.get('net_price'))
    product.gross_price = decimal.Decimal(dictionary.get('gross_price'))
    product.sale_price = decimal.Decimal(dictionary.get('sale_price'))
    product.r120_price = decimal.Decimal(dictionary.get('r120_price'))
    product.r110_price = decimal.Decimal(dictionary.get('r110_price'))
    product.r100_price = decimal.Decimal(dictionary.get('r100_price'))
    product.web_price = decimal.Decimal(dictionary.get('web_price'))
    product.rm_collection = dictionary.get('rm_collection')
    product.color = dictionary.get('color')
    product.category = dictionary.get('category')
    product.variants = []
    for var in dictionary.get('variants'):
        variant = DaneaVariant()
        variant.qty = var.get('qty')
        variant.size = var.get('size')
        variant.barcode = var.get('barcode')
        variant.original_size = var.get('original_size')
        product.variants.append(variant)
    return product
