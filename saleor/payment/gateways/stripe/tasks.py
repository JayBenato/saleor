import stripe
from saleor.celeryconf import app
from saleor.payment.gateways.stripe import utils
from saleor.product.models import Product


@app.task
def stripe_create_or_update_product(product_id: str, configuration):
    product: Product = Product.objects.get(id=product_id)
    stripe.api_key = configuration["Secret API key"]
    name = product.private_metadata.get("rm_code") \
           + " - " + product.private_metadata.get("original_color")
    statement_desc = product.category.name.__str__().split(" ", 1)[0]
    try:
        response = stripe.Product.retrieve(product.id.__str__())
        if response.get("id") == product.id.__str__():
            stripe.Product.modify(
                response.get("id"),
                name=name,
                images=utils.get_product_images_for_stripe(product),
                url=utils.get_product_url_for_stripe(product),
                statement_descriptor=statement_desc
            )
    except:
        stripe.Product.create(
            id=product.id.__str__(),
            name=name,
            images=utils.get_product_images_for_stripe(product),
            url=utils.get_product_url_for_stripe(product),
            statement_descriptor=statement_desc
        )
        response = stripe.Price.create(
            currency="eur",
            product=product.id.__str__(),
            unit_amount_decimal=utils.get_product_price(product)
        )
        product.private_metadata["stripe_price_id"] = response.get("id")


@app.task
def stripe_create_product(product_id, configuration):
    product: Product = Product.objects.get(id=product_id)
    stripe.api_key = configuration["Secret API key"]
    name = product.private_metadata.get(
        "rm_code") + " - " + product.private_metadata.get("original_color")
    stripe.Product.create(
        id=product.id.__str__(),
        name=name,
        images=utils.get_product_images_for_stripe(product),
        url=utils.get_product_url_for_stripe(product),
        statement_descriptor=product.category.name.__str__()
    )


@app.task
def stripe_full_products_sync(configuration):
    for product in Product.objects.all():
        stripe_create_or_update_product.delay(product.id, configuration)
