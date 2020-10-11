import logging
from prices import Money
from django.db import transaction
from saleor.account.models import Address
from saleor.plugins.danea.xml_converter import DaneaProduct
from saleor.shipping.models import ShippingZone
from saleor.warehouse.models import Warehouse, Stock
from saleor.product.utils.attributes import associate_attribute_values_to_instance
from saleor.product.models import Product, ProductVariant, Attribute, ProductType, \
    Category, Collection, AttributeValue

logger = logging.getLogger(__name__)


def update_product(product: DaneaProduct, warehouse: str):
    warehouse = find_warehouse(warehouse)
    django_product = Product.objects.get(slug=product.code)
    django_product.price = Money(product.gross_price, "EUR")
    django_product.save()
    # TODO Update private metadata dict
    # TODO Update names
    # TODO Update collection
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
        price=Money(product.gross_price, "EUR"),
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
        )
        variant_meta = {
            'original_size': variant.size
        }
        var.store_value_in_private_metadata(items=variant_meta)
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
    if Warehouse.objects.filter(slug=warehouse.lower()).exists():
        warehouse = Warehouse.objects.get(slug=warehouse.lower())
    else:
        warehouse = Warehouse.objects.create(
            name=warehouse.lower(),
            slug=warehouse.lower(),
            company_name='Toda Joia Fitness',
            # TODO generate address logic for new warehouses.
            address=Address.objects.get(
                company_name='TodaJoia di Cleonice Maria Soares Dias'),
            shipping_zones=ShippingZone.objects.get(name='Europe')
        )
    return warehouse


def find_and_associate_size(var, variant):
    attribute = Attribute.objects.get(slug='size')
    attribute_value = AttributeValue.objects.get(
        slug=Utils.parse_size(variant.size)
    )
    associate_attribute_values_to_instance(var, attribute, attribute_value)


def find_and_associate_color(persisted_product, color):
    logger.info('Finding color ....')
    attribute = Attribute.objects.get(slug='color')
    color_value = AttributeValue.objects.get(slug=color)
    associate_attribute_values_to_instance(
        persisted_product,
        attribute,
        color_value
    )


def find_and_associate_material(persisted_product, material):
    logger.info('Finding material ....')
    material_attribute = Attribute.objects.get(slug='material')
    if material != '':
        material_value = AttributeValue.objects.get(slug=material)
        associate_attribute_values_to_instance(
            persisted_product,
            material_attribute,
            material_value
        )
    else:
        logger.error('Unable to find material...')


def insert_product_into_collection(persisted_product, collection):
    logger.info('Finding collection ....')
    if collection != 'None':
        collection = Collection.objects.get(slug=collection)
        collection.products.add(persisted_product)
    else:
        logger.error('Unable to find collection')


class Utils:

    @staticmethod
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
        elif color.startswith('am') :
            return 'yellow'
        else:
            return None

    @staticmethod
    def parse_size(product_name: str) -> str:
        product_name = product_name.lower()
        if 's' in product_name or 'p' in product_name:
            return 's'
        elif 'm' in product_name:
            return 'm'
        elif 'l' in product_name or 'g' in product_name:
            return 'l'
        else:
            return 'xl'

    @staticmethod
    def parse_type(product_name: str) -> str:
        product_name = product_name.lower()
        if 'leggings' in product_name or 'calca' in product_name \
                or 'short' in product_name or 'capri' in product_name \
                or 'pinocchietto' in product_name or 'bermuda' in product_name:
            return 'pants'
        if 'jumpsuit' in product_name or 'tuta' in product_name:
            return 'body'
        return 'top'

    @staticmethod
    def parse_material(product_name: str):
        product_name = product_name.lower()
        if 'revers' or 'lycra' or 'sublime' or 'double' in product_name:
            return 'lycra'
        elif 'supplex' in product_name:
            return 'supplex'
        elif 'cir' in product_name:
            return 'cire'
        elif 'aqua' in product_name:
            return 'aqua-fit'
        elif 'atlanta' in product_name:
            return 'atlanta'
        elif 'emana' in product_name:
            return 'emana'
        else:
            return None

    @staticmethod
    def parse_category(product_name: str):
        product_name = product_name.lower()
        if 'maglia' in product_name or 'maglione' in product_name \
                or 'blusa' in product_name or 'vest' in product_name \
                or 't-shirt' in product_name or 'polo' in product_name \
                or 'manicotti' in product_name:
            return 'jersey'
        if 'jumpsuit' in product_name or 'tuta  intera' in product_name \
                or 'macacao' in product_name:
            return 'jumpsuit'
        if 'capri' in product_name or 'pinocchietto' in product_name \
                or 'corsario' in product_name:
            return 'capri'
        if 'legg' in product_name or 'jeggings' in product_name:
            return 'leggings'
        if 'calca' in product_name or 'tuta' in product_name \
                or 'pantalone' in product_name:
            return 'joggers'
        if 'pantaloncino' in product_name or 'short' in product_name \
                or 'bermuda' in product_name or 'ciclista' in product_name:
            return 'shorts'
        if 'top' in product_name or 'reggiseno' in product_name:
            return 'sports-bra'
        if 'canot' in product_name or 'regata' in product_name:
            return 'tank-top'
        if 'giacca' in product_name or 'felpa' in product_name \
                or 'jaqueta' in product_name:
            return 'jacket'
        if 'body' in product_name:
            return 'body'
        if 'gonna' in product_name or 'saia' in product_name:
            return 'skirt'
        return None

    @staticmethod
    def parse_collection(product_name: str):
        product_name = product_name.lower()
        if 'reverse' in product_name or 'double' in product_name:
            return 'reverse'
        if 'jeans' in product_name:
            return 'fake-jeans'
        return None

    @staticmethod
    def extract_rm_code(product_name: str):
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

    @staticmethod
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

    @staticmethod
    def validate_name(name: str) -> bool:
        name = name.lower()
        if 'calca' in name:
            return False
        if 'blusa' in name:
            return False
        if 'saia' in name:
            return False
        if 'bermuda' in name:
            return False
        if 'macacao' in name:
            return False
        if 'jeggings' in name:
            return False
        if 'vest legging' in name:
            return False
        if 'manicotti' in name:
            return False
        if 'regata' in name:
            return False
        return True
