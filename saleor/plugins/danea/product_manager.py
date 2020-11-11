from prices import Money
from django.db import transaction
from saleor.plugins.danea.xml_converter import DaneaProduct
from saleor.warehouse.models import Warehouse, Stock
from saleor.product.utils.attributes import associate_attribute_values_to_instance
from saleor.product.models import Product, ProductVariant, Attribute, ProductType, \
    Category, Collection, AttributeValue


def update_product(product: DaneaProduct, warehouse: str):
    warehouse = find_warehouse(warehouse)
    django_product: Product = Product.objects.get(slug=product.code)
    django_product.price = Money(product.gross_price, "EUR")
    django_product.name = product.name
    django_product.save()
    for variant in product.variants:
        with transaction.atomic():
            try:
                var = ProductVariant.objects.get(sku=variant.barcode)
            except:
                var = ProductVariant.objects.create(
                    product=django_product,
                    sku=variant.barcode,
                    name=variant.size
                )
            try:
                stock = Stock.objects.get(
                    product_variant_id=var.id,
                    warehouse_id=warehouse.id
                )
            except:
                stock = Stock.objects.create(
                    warehouse=warehouse,
                    product_variant=var,
                )
            if int(variant.qty) > 0:
                stock.quantity = variant.qty
            else:
                stock.quantity = 0
            stock.save()


def store_private_meta(persisted_product, product):
    private_meta = {
        'original_name': product.original_name,
        'original_color': product.original_color,
        'rm_code': product.rm_code,
        'danea_code': product.code,
        'collection': product.collection,
        'r_110': product.r110_price,
        'r_120': product.r120_price,
        'r_100': product.r100_price,
        'web_price': product.web_price,
        'sale_price': product.sale_price,
        'net_price': product.net_price,
        'internal_id': product.internal_id
    }
    persisted_product.store_value_in_private_metadata(items=private_meta)
    persisted_product.save()


def generate_product(product: DaneaProduct, warehouse: str):
    warehouse = find_warehouse(warehouse)
    product_type = ProductType.objects.get(slug=product.type)
    category = Category.objects.get(slug=product.category)
    persisted_product = Product.objects.create(
        name=product.name + ' (' + product.rm_code + ')',
        slug=product.code,
        category=category,
        product_type=product_type,
        is_published=True,
    )
    store_private_meta(persisted_product, product)
    for variant in product.variants:
        var = ProductVariant.objects.create(
            product=persisted_product,
            sku=variant.barcode,
            name=variant.size,
            price_amount=product.gross_price
        )
        if int(variant.qty) > 0:
            Stock.objects.create(
                warehouse=warehouse,
                product_variant=var,
                quantity=variant.qty,
            )
        else:
            Stock.objects.create(
                warehouse=warehouse,
                product_variant=var,
                quantity=0,
            )
        find_and_associate_size(var, variant)
    find_and_associate_color(persisted_product, product.color)
    find_and_associate_material(persisted_product, product.material)
    insert_product_into_collection(persisted_product, product.collection)


def find_warehouse(warehouse: str) -> Warehouse:
    return Warehouse.objects.get(slug=warehouse.lower())


def find_and_associate_size(var, variant):
    attribute = Attribute.objects.get(slug='size')
    attribute_value = AttributeValue.objects.get(slug=variant.size)
    associate_attribute_values_to_instance(var, attribute, attribute_value)


def find_and_associate_color(persisted_product, color):
    attribute = Attribute.objects.get(slug='color')
    color_value = AttributeValue.objects.get(slug=color)
    associate_attribute_values_to_instance(
        persisted_product,
        attribute,
        color_value
    )


def find_and_associate_material(persisted_product, material):
    material_attribute = Attribute.objects.get(slug='material')
    material_value = AttributeValue.objects.get(slug=material)
    associate_attribute_values_to_instance(
        persisted_product,
        material_attribute,
        material_value
    )


def insert_product_into_collection(persisted_product, collection):
    if collection is not 'N':
        collection = Collection.objects.get(slug=collection)
        collection.products.add(persisted_product)
