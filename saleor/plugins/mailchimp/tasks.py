from django.contrib.sites.models import Site
from saleor.account.models import User
from saleor.celeryconf import app
from saleor.plugins.mailchimp import utils
from saleor.product.models import Product


@app.task
def add_mailchimp_product(product_id, configuration: {}):
    import mailchimp_marketing as MailchimpMarketing
    product: Product = Product.objects.get(id=product_id)
    client = MailchimpMarketing.Client()
    client.set_config({
        "api_key": configuration["API Key"],
        "server": configuration["Server Prefix"]
    })
    current_site = Site.objects.get_current()
    image_array = utils.get_product_images_array(product, current_site)
    variants_array = utils.get_product_variants_array(product)
    product_url = utils.get_product_url(product, current_site)
    if image_array and variants_array and product_url:
        client.ecommerce.add_store_product(
            configuration["Store ID"],
            {
                "id": product.id.__str__(),
                "url": product_url,
                "title": product.name,
                "handle": product.private_metadata.get("danea_code"),
                "type": product.product_type.name,
                "image_url": image_array.pop().get("url"),
                "images": image_array,
                "variants": variants_array
            }
        )


@app.task
def update_mailchimp_product(product_id: str, configuration: {}):
    import mailchimp_marketing as MailchimpMarketing
    product: Product = Product.objects.get(id=product_id)
    client = MailchimpMarketing.Client()
    client.set_config({
        "api_key": configuration["API Key"],
        "server": configuration["Server Prefix"]
    })
    current_site = Site.objects.get_current()
    image_array = utils.get_product_images_array(product, current_site)
    client.ecommerce.update_store_product(
        configuration["Store ID"],
        product.id.__str__(),
        {
            "url": utils.get_product_url(product, current_site),
            "title": product.name,
            "handle": product.private_metadata.get("danea_code"),
            "type": product.product_type.name,
            "image_url": image_array.pop().get("url"),
            "images": image_array,
            "variants": utils.get_product_variants_array(product)
        }
    )
    for variant in product.variants:
        client.ecommerce.update_product_variant(
            configuration["Store ID"],
            product.id.__str__(),
            variant.id.__str__(),
            {
                "price": variant.get_price(),
                "inventory_quantity": utils.get_variant_stock_quantity(variant)
            }
        )


@app.task
def create_mailchimp_customer(customer_id, configuration):
    import mailchimp_marketing as MailchimpMarketing
    customer: User = User.objects.get(id=customer_id)
    client = MailchimpMarketing.Client()
    client.set_config({
        "api_key": configuration["API Key"],
        "server": configuration["Server Prefix"]
    })
    client.lists.add_list_member(
        configuration["List ID"],
        {
            "email_address": customer.email.__str__(),
            "status": "subscribed"
        }
    )


@app.task
def mailchimp_full_products_sync(configuration):
    import mailchimp_marketing as MailchimpMarketing
    client = MailchimpMarketing.Client()
    client.set_config({
        "api_key": configuration["API Key"],
        "server": configuration["Server Prefix"]
    })
    client.ecommerce.delete_store(configuration["Store ID"])
    client.ecommerce.add_store(
        {
            "id": configuration["Store ID"],
            "list_id": configuration["List ID"],
            "name": "TodaJoia Fitness Fashion",
            "currency_code": "EUR",
            "platform": "saleor",
            "email_address": "info@todajoia.com"
        }
    )
    for product in Product.objects.all():
        add_mailchimp_product.delay(product.id,configuration)
