from .danea_dataclass import DaneaProduct, DaneaVariant
from .product_manager import generate_product, update_product
from ...celeryconf import app


@app.task
def generate_product_task(product, warehouse):
    product = to_danea_product(product)
    generate_product(product, warehouse)


@app.task
def update_product_task(product, warehouse):
    product = to_danea_product(product)
    update_product(product, warehouse)


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
    product.net_price = dictionary.get('net_price')
    product.gross_price = dictionary.get('gross_price')
    product.sale_price = dictionary.get('sale_price')
    product.r120_price = dictionary.get('r120_price')
    product.r110_price = dictionary.get('r110_price')
    product.r100_price = dictionary.get('r100_price')
    product.web_price = dictionary.get('web_price')
    product.rm_collection = dictionary.get('rm_collection')
    product.color = dictionary.get('color')
    product.category = dictionary.get('category')
    product.variants = []
    for var in dictionary.get('variants'):
        variant = DaneaVariant()
        variant.qty = var.get('qty')
        variant.size = var.get('size')
        variant.barcode = var.get('barcode')
        product.variants.append(variant)
    return product
