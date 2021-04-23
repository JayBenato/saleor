from django.contrib.syndication.views import add_domain
from saleor.product.models import Product, ProductVariant
from saleor.warehouse.models import Stock


def get_product_images_array(product: Product, current_site) -> []:
    image_array = []
    for image in product.images.all():
        image_array.append(
            {
                "id": image.id.__str__(),
                "url": add_domain(current_site.domain, image.image.url, False),
            }
        )
    return image_array


def get_variants_ids_array(product: Product) -> []:
    id_array = []
    for variant in product.variants.all():
        id_array.append(variant.id.__str__())
    return id_array


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
    for variant in product.variants.all():
        stock = Stock.objects.get(
            product_variant_id=variant.id,
            warehouse_id="f251c71c-078e-4379-b69b-241f63619199"
        )
        variants.append(
            {
                "id": variant.id.__str__(),
                "sku": stock.id.__str__(),
                "title": variant.name,
                "price": variant.get_price().amount.__str__(),
                "inventory_quantity": stock.quantity
            }
        )
    return variants


def get_variant_stock_quantity(variant: ProductVariant) -> int:
    return Stock.objects.get(
        product_variant_id=variant.id,
        warehouse_id="f251c71c-078e-4379-b69b-241f63619199"
    ).quantity


def get_checkout_lines(checkout):
    variants = []
    for variant in checkout.resolve_lines():
        variants.append(
            {
                "product_id": variant.product.id.__str__(),
                "product_variant_id": variant.id,
                "price": variant.get_price(),
                "quantity": variant.quantity
            }
        )
    return variants
