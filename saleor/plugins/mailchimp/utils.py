from django.contrib.syndication.views import add_domain

from saleor.checkout.models import Checkout
from saleor.product.models import Product, ProductVariant
from saleor.warehouse.models import Stock


def get_product_images_array(product: Product, current_site) -> []:
    image_array = []
    for image in product.images:
        image_array.append(
            {
                "id": image.id,
                "url": add_domain(current_site.domain, image.url, False),
                "variant_ids": get_variants_ids_array(product)
            }
        )
    return image_array


def get_variants_ids_array(product: Product) -> []:
    id_array = []
    for variant in product.variants:
        id_array.append(variant.id.__str__())


def get_product_url(product: Product, current_site):
    product_url = product.name.replace("-", "")
    product_url = product_url.replace(")", "")
    product_url = product_url.replace("(", "")
    product_url = product_url.replace("  ", " ")
    product_url = product_url.replace(" ", "-")
    product_url = "/product/" + product_url + "/" + str(product.id) + "/"
    return add_domain(current_site.domain, product_url, True)


def get_product_variants_array(product: "Product") -> []:
    variants = []
    for variant in product.variants:
        stock = Stock.objects.get(
            product_variant_id=variant.id,
            warehouse_id=variant.private_metadata.get("warehouse_id")
        )
        variants.append(
            {
                "id": variant.id,
                "sku": stock.id.__str__(),
                "title": variant.name,
                "price": variant.get_price(),
                "inventory_quantity": variant.quantity
            }
        )
    return variants


def get_variant_stock_quantity(variant: ProductVariant) -> int:
    return Stock.objects.get(
        product_variant_id=variant.id,
        warehouse_id=variant.private_metadata.get("warehouse_id")
    ).quantity


def get_customer_from_checkout(checkout: "Checkout"):
    return {
        "email_address" : checkout.get_customer_email(),
        "id": checkout.
    }


def get_checkout_total(checkout):
    return None


def get_checkout_lines(checkout):
    return None
