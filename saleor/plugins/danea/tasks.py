import decimal
import datetime

from . import DaneaProduct, DaneaVariant
from ...data_feeds.google_merchant import update_feed
from ...celeryconf import app
from django.db import transaction
from saleor.discount.models import Sale
from saleor.plugins.manager import get_plugins_manager
from saleor.plugins.models import PluginConfiguration, DaneaCollectionsMappings, \
    DaneaAttributeValuesMappings
from saleor.warehouse.models import Warehouse, Stock
from saleor.product.utils.attributes import associate_attribute_values_to_instance
from saleor.product.models import Product, ProductVariant, Attribute, ProductType, \
    Category, Collection, AttributeValue, CollectionProduct


@app.task
def generate_product_task(product, warehouse):
    product = to_danea_product(product)
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
    default_variant_qty = 0
    default_variant = None
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
            if default_variant_qty < variant.qty:
                default_variant = variant
                default_variant_qty = variant.qty
        else:
            Stock.objects.create(
                warehouse=warehouse,
                product_variant=var,
                quantity=0,
            )
        find_and_associate_size(var, variant)
        store_variant_private_meta(var, variant, warehouse)
    set_default_variant(default_variant, persisted_product)
    find_and_associate_color(persisted_product, product.color)
    find_and_associate_material(persisted_product, product.material)
    insert_product_into_matching_collections(persisted_product)
    check_and_add_product_to_new_collection(persisted_product, product.rm_collection)
    manage_discounts(persisted_product, product)
    get_plugins_manager().product_created(persisted_product)


@app.task
def update_product_task(product, warehouse):
    product = to_danea_product(product)
    warehouse = find_warehouse(warehouse)
    django_product: Product = Product.objects.get(slug=product.code)
    django_product.name = product.name + ' (' + product.rm_code + ')' + ' - ' + product.original_color
    django_product.description = product.rm_code
    django_product.updated_at = datetime.date.today()
    django_product.is_published = True
    django_product.visible_in_listings = True
    django_product.category = Category.objects.get(slug=product.category.lower())
    django_product.save()
    is_stock_positive: bool = False
    default_variant_qty = 0
    default_variant = None
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
                is_stock_positive = True
                stock.quantity = variant.qty
                if default_variant_qty < variant.qty:
                    default_variant = variant
                    default_variant_qty = variant.qty
            else:
                stock.quantity = 0
            stock.save()
            store_variant_private_meta(var, variant, warehouse)
        if is_stock_positive:
            django_product.is_published = True
            django_product.visible_in_listings = True
            django_product.available_for_purchase = datetime.date.today()
            django_product.save()
        find_and_associate_size(var, variant)
    set_default_variant(default_variant, django_product)
    find_and_associate_color(django_product, product.color)
    find_and_associate_material(django_product, product.material)
    insert_product_into_matching_collections(django_product)
    check_and_add_product_to_new_collection(django_product, product.rm_collection)
    manage_discounts(django_product, product)
    get_plugins_manager().product_updated(django_product)


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


@app.task
def reprocess_product_attributes(id):
    product: Product = Product.objects.get(id=id)
    color = product.private_metadata.get("original_color")
    material = product.private_metadata.get("material")
    collection = product.private_metadata.get("collection")
    rm_collection = product.private_metadata.get("rm_collection")
    category = product.private_metadata.get("category")
    if category:
        find_and_associate_category(product, category)
    if color:
        color = color[:2].lower()
        color = DaneaAttributeValuesMappings.objects.get(
            danea_field=color
        ).saleor_attribute_value_slug
        find_and_associate_color(product, color)
    if material:
        find_and_associate_material(product, material)
    if collection:
        insert_product_into_matching_collections(product)
    if rm_collection:
        check_and_add_product_to_new_collection(product, rm_collection)
    variant_qty = 0
    default_variant = None
    # TODO find a way to get correct warehouse
    warehouse = find_warehouse('02 principale')
    for variant in product.variants.filter(product=product.id):
        stock = Stock.objects.get(
            product_variant_id=variant.id,
            warehouse_id=warehouse.id
        )
        if stock.quantity > variant_qty:
            variant_qty = stock.quantity
            default_variant = variant
    set_default_variant(default_variant, product)


@app.task
def reprocess_products_attributes():
    for product in Product.objects.all():
        reprocess_product_attributes.delay(product.id.__str__())


def manage_discounts(persisted_product: Product, danea_product: DaneaProduct):
    if danea_product.web_price is not None and danea_product.web_price > 0:
        collection = Collection.objects.get(slug='outlet')
        d_amount = danea_product.gross_price - danea_product.web_price
        if Sale.objects.filter(name=danea_product.internal_id).exists():
            sale = Sale.objects.get(name=danea_product.internal_id)
            if sale.value != d_amount:
                sale.value = d_amount
                sale.save()
        else:
            sale = Sale.objects.create(
                name=danea_product.internal_id,
                type='fixed',
                value=d_amount,
                start_date=datetime.date.today()
            )
            collection.products.add(persisted_product)
            sale.products.add(persisted_product)
    else:
        if Sale.objects.filter(name=danea_product.internal_id).exists():
            collection = Collection.objects.get(slug='outlet')
            sale = Sale.objects.get(name=danea_product.internal_id)
            sale.products.remove(persisted_product)
            if CollectionProduct.objects.filter(collection=collection.id,
                                                product=persisted_product.id).exists():
                collection.products.remove(persisted_product)


def check_and_add_product_to_new_collection(product: Product, rm_collection):
    plugin_config = PluginConfiguration.objects.get(
        identifier='todajoia.integration.danea'
    )
    configuration = {item["name"]: item["value"] for item in plugin_config}
    if rm_collection == configuration["Latest Collection"]:
        collection = Collection.objects.get(slug='new')
        collection.objects.products.add(product)


def insert_product_into_matching_collections(persisted_product):
    for c in DaneaCollectionsMappings.objects.all():
        if c.keyword in persisted_product.name:
            c.products.add(persisted_product)


def store_private_meta(persisted_product, product):
    private_meta = {
        'original_name': product.original_name,
        'original_color': product.original_color,
        'rm_code': product.rm_code,
        'danea_code': product.code,
        'r_110': product.r110_price,
        'r_120': product.r120_price,
        'r_100': product.r100_price,
        'web_price': product.web_price,
        'sale_price': product.sale_price,
        'net_price': product.net_price,
        'internal_id': product.internal_id,
        'material': product.material,
        'rm_collection': product.rm_collection,
        'category': product.category
    }
    persisted_product.store_value_in_private_metadata(items=private_meta)
    persisted_product.save()


def store_variant_private_meta(var: ProductVariant, variant: DaneaVariant,
                               warehouse: Warehouse):
    private_meta = {
        'original_size': variant.original_size.__str__(),
        'warehouse_id': warehouse.id,
    }
    var.store_value_in_private_metadata(items=private_meta)
    var.save()


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


def find_and_associate_category(product: Product, category: str):
    if Category.objects.get(slug=category.lower()).exists():
        product.category = Category.objects.get(slug=category.lower())


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


def set_default_variant(variant: ProductVariant, product: Product):
    if variant is not None:
        product.default_variant = variant
        product.save()
