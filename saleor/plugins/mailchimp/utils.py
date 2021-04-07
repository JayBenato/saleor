import math
from collections import Iterable

from django.contrib.sites.models import Site
from django.contrib.syndication.views import add_domain
from django.utils import timezone
from django.utils.encoding import smart_text
from django_countries.fields import Country

from saleor import settings
from saleor.core.taxes import charge_taxes_on_shipping
from saleor.discount import DiscountInfo
from saleor.discount.utils import fetch_discounts
from saleor.plugins.manager import get_plugins_manager
from saleor.product.models import ProductVariant, Category, Attribute, AttributeValue, \
    Product
from saleor.warehouse.availability import is_variant_in_stock
from saleor.warehouse.models import Stock


def get_feed_items():
    items = ProductVariant.objects.all()
    items = items.select_related("product")
    items = items.prefetch_related(
        "images",
        "product__category",
        "product__images",
        "product__product_type__product_attributes",
        "product__product_type__variant_attributes",
    )
    return items


def item_price(item: ProductVariant):
    price = item.get_price(discounts=None)
    return "%s %s" % (math.trunc(price.amount), price.currency)


def item_sale_price(item: ProductVariant, discounts: Iterable[DiscountInfo]):
    sale_price = item.get_price(discounts=discounts)
    return "%s %s" % (math.trunc(sale_price.amount), sale_price.currency)


def item_attributes(
        item: ProductVariant,
        categories,
        category_paths,
        current_site,
        discounts: Iterable[DiscountInfo],
        attributes_dict,
        attribute_values_dict,
        is_charge_taxes_on_shipping: bool,
):
    product_data = {
        "id": item_id(item),
        "title": item_title(item),
        "description": item_description(item),
        "condition": item_condition(item),
        "mpn": item_mpn(item),
        "item_group_id": item_group_id(item),
        "availability": item_availability(item),
        "link": item_link(item, current_site)
    }

    image_link = item_image_link(item, current_site)
    if image_link:
        product_data["image_link"] = image_link

    price = item_price(item)
    product_data["price"] = price
    sale_price = item_sale_price(item, discounts)
    if sale_price != price:
        product_data["sale_price"] = sale_price

    tax = item_tax(item, discounts, is_charge_taxes_on_shipping)
    if tax:
        product_data["tax"] = tax

    brand = item_brand(item, attributes_dict, attribute_values_dict)
    if brand:
        product_data["brand"] = brand

    return product_data


def item_id(item: ProductVariant):
    return item.sku


def item_mpn(item: ProductVariant):
    return str(item.sku)


def item_guid(item: ProductVariant):
    return item.sku


def item_title(item: ProductVariant):
    return item.display_product()


def item_description(item: ProductVariant):
    return item.product.plain_text_description[:100]


def item_condition(item: ProductVariant):
    """Return a valid item condition.

    Allowed values: new, refurbished, and used.
    Read more:
    https://support.google.com/merchants/answer/6324469
    """
    return "new"


def item_brand(item: ProductVariant, attributes_dict, attribute_values_dict):
    """Return an item brand.

    This field is required.
    Read more:
    https://support.google.com/merchants/answer/6324351?hl=en&ref_topic=6324338
    """
    brand = None
    brand_attribute_pk = attributes_dict.get("brand")
    publisher_attribute_pk = attributes_dict.get("publisher")

    if brand_attribute_pk:
        brand = item.attributes.get(str(brand_attribute_pk))
        if brand is None:
            brand = item.product.attributes.get(str(brand_attribute_pk))

    if brand is None and publisher_attribute_pk is not None:
        brand = item.attributes.get(str(publisher_attribute_pk))
        if brand is None:
            brand = item.product.attributes.get(str(publisher_attribute_pk))

    if brand:
        brand_name = attribute_values_dict.get(brand)
        if brand_name is not None:
            return brand_name
    return brand


def item_tax(
        item: ProductVariant,
        discounts: Iterable[DiscountInfo],
        is_charge_taxes_on_shipping: bool,
):
    """Return item tax.

    For some countries you need to set tax info
    Read more:
    https://support.google.com/merchants/answer/6324454
    """
    country = Country(settings.DEFAULT_COUNTRY)
    tax_rate = get_plugins_manager().get_tax_rate_percentage_value(
        item.product.product_type, country
    )
    if tax_rate:
        tax_ship = "yes" if is_charge_taxes_on_shipping else "no"
        return "%s::%s:%s" % (country.code, tax_rate, tax_ship)
    return None


def item_group_id(item: ProductVariant):
    return str(item.product.pk)


def item_image_link_array(item: Product, current_site) -> []:
    image_array = []
    for image in item.images:
        image_array.append(add_domain(current_site.domain, image.url, False))
    return image_array

def item_link(item: ProductVariant, current_site):
    product_url = item.product.name.replace("-", "")
    product_url = product_url.replace(")", "")
    product_url = product_url.replace("(", "")
    product_url = product_url.replace("  ", " ")
    product_url = product_url.replace(" ", "-")
    product_url = "/product/" + product_url + "/" + str(item.product.id) + "/"
    return add_domain(current_site.domain, product_url, True)


def item_availability(item: ProductVariant):
    if is_variant_in_stock(item, settings.DEFAULT_COUNTRY):
        return "in stock"
    return "out of stock"

def mailchimp_get_product_images_url(self, product: "Product"):
    pass

def mailchimp_get_product_variants_array(product: "Product") -> []:
    variants :[ProductVariant] = [ProductVariant]
    for variant in product.variants :
        variants.append(
            {
                "id": variant.id,
                "title" : variant.name,
                "price" : variant.get_price(),
                "inventory quantity" : Stock.objects.get(
                    product_variant_id=variant.id,
                    warehouse_id=variant.private_metadata.get("warehouse_id")
                )
            }
        )
    return variants

def mailchimp_get_product_url(self, product: "Product"):
    pass


#         TODO make this method a manage.py command
def mailchimp_sync_products():
    is_charge_taxes_on_shipping = charge_taxes_on_shipping()
    categories = Category.objects.all()
    discounts = fetch_discounts(timezone.now())
    attributes_dict = {a.slug: a.pk for a in Attribute.objects.all()}
    attribute_values_dict = {
        smart_text(a.pk): smart_text(a) for a in AttributeValue.objects.all()
    }
    category_paths = {}
    current_site = Site.objects.get_current()
    for item in get_feed_items():
        item_data = item_attributes(
            item,
            categories,
            category_paths,
            current_site,
            discounts,
            attributes_dict,
            attribute_values_dict,
            is_charge_taxes_on_shipping,
        )
        create_mailchimp_product(item_data)


def create_mailchimp_product(item_data):
    pass
