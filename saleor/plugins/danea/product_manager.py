import datetime
from django.db import transaction
from saleor.plugins.danea.danea_dataclass import DaneaProduct, DaneaVariant
from saleor.warehouse.models import Warehouse, Stock
from saleor.product.utils.attributes import associate_attribute_values_to_instance
from saleor.product.models import Product, ProductVariant, Attribute, ProductType, \
    Category, Collection, AttributeValue


def update_product(product: DaneaProduct, warehouse: str):
    warehouse = find_warehouse(warehouse)
    django_product: Product = Product.objects.get(slug=product.code)
    django_product.name = product.name + ' (' + product.rm_code + ')' + ' - ' + product.original_color
    django_product.description = product.rm_code
    django_product.updated_at = datetime.date.today()
    django_product.is_published = True
    django_product.visible_in_listings = True
    django_product.category = Category.objects.get(slug=product.category.lower())
    django_product.save()
    insert_product_into_collection(django_product, product.collection)
    for variant in product.variants:
        with transaction.atomic():
            try:
                var = ProductVariant.objects.get(sku=variant.barcode)
                var.price_amount = product.gross_price
            except:
                var = ProductVariant.objects.create(
                    product=django_product,
                    sku=variant.barcode,
                    name=variant.size,
                    price_amount=product.gross_price
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
            store_variant_private_meta(var, variant)


def store_variant_private_meta(var: ProductVariant, variant: DaneaVariant):
    private_meta = {
        'original_size': variant.original_size.__str__()
    }
    var.store_value_in_private_metadata(items=private_meta)
    var.save()


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
    product_type = ProductType.objects.get(slug=product.type.lower())
    category = Category.objects.get(slug=product.category.lower())
    persisted_product = Product.objects.create(
        name=product.name + ' (' + product.rm_code + ')' + ' - ' + product.original_color,
        slug=product.code,
        category=category,
        product_type=product_type,
        is_published=True,
        available_for_purchase=datetime.date.today(),
        visible_in_listings=True,
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
        store_variant_private_meta(var, variant)
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
    if collection != 'N':
        collection = Collection.objects.get(slug=collection)
        collection.products.add(persisted_product)
