import logging
from typing import Any
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.utils.translation import pgettext_lazy
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

from saleor.checkout import calculations
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.mailchimp import utils
from saleor.plugins.models import PluginConfiguration
from saleor.product.models import Product

logger = logging.getLogger(__name__)


class MailChimpPlugin(BasePlugin):
    PLUGIN_NAME = "MailChimpPlugin"
    PLUGIN_ID = "todajoia.integration.mailchimp"
    DEFAULT_CONFIGURATION = [
        {"name": "API Key", "value": None},
        {"name": "Server Prefix", "value": None},
        {"name": "List ID", "value": None},
        {"name": "Store ID", "value": None},
        {"name": "Full Sync", "value": False},
    ]
    CONFIG_STRUCTURE = {
        "API Key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide your mailchimp api key"
            ),
            "label": pgettext_lazy("Plugin label", "API Key"),
        },
        "Server Prefix": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide your mail chimp server prefix"
            ),
            "label": pgettext_lazy("Plugin label", "Server Prefix"),
        },
        "List ID": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide your mail chimp server prefix"
            ),
            "label": pgettext_lazy("Plugin label", "List ID"),
        },
        "Store ID": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide your mail chimp store ID"
            ),
            "label": pgettext_lazy("Plugin label", "MailChimp Store ID"),
        },
        "Full Sync": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text", "Plugin will trigger a full sync on validate"
            ),
            "label": pgettext_lazy("Plugin label", "Full Sync"),
        },
    }
    client = MailchimpMarketing.Client()
    store_id = 1
    list_id = None

    @classmethod
    def validate_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        """Validate if provided configuration is correct."""
        missing_fields = []
        api_errors = []
        configuration = plugin_configuration.configuration
        configuration = {item["name"]: item["value"] for item in configuration}
        if not configuration["API Key"]:
            missing_fields.append("API Key")
        if not configuration["Server Prefix"]:
            missing_fields.append("Server Prefix")
        if not configuration["List ID"]:
            missing_fields.append("List ID")
        if not configuration["Store ID"]:
            missing_fields.append("Store ID")
        if not missing_fields:
            try:
                cls.client.set_config({
                    "api_key": configuration["API Key"],
                    "server": configuration["Server Prefix"]
                })
                cls.client.ping.get()
                cls.client.lists.get_list(configuration["List ID"])
                cls.client.ecommerce.get_store(configuration["Store ID"])
                cls.store_id = configuration["Store ID"]
                cls.list_id = configuration["List ID"]
            except ApiClientError as error:
                logger.error("Error: {}".format(error.text))
                api_errors.append("Wrong Config : " + error.text)
        if plugin_configuration.active and missing_fields:
            error_msg = (
                "To enable a plugin, you need to provide values for the "
                "following fields: "
            )
            raise ValidationError(error_msg + ", ".join(missing_fields))
        if plugin_configuration.active and api_errors:
            error_msg = "MailChimp API :"
            raise ValidationError(error_msg + ", ".join(api_errors))
        if configuration["Full Sync"] is True:
            cls.full_sync(cls)

    def product_updated(self, product: "Product", previous_value: Any) -> Any:
        try:
            current_site = Site.objects.get_current()
            image_array = utils.get_product_images_array(product, current_site)
            self.client.ecommerce.update_store_product(
                self.store_id,
                product.id,
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
                self.client.ecommerce.update_product_variant(
                    self.configuration["Store ID"],
                    product.id.__str__(),
                    variant.id.__str__(),
                    {
                        "price": variant.get_price(),
                        "inventory_quantity": utils.get_variant_stock_quantity(variant)
                    }
                )
        except ApiClientError as error:
            logger.error("Error: {}".format(error.text))

    # TODO make this a celery task
    def product_created(self, product: "Product", previous_value: Any) -> Any:
        try:
            current_site = Site.objects.get_current()
            image_array = utils.get_product_images_array(product, current_site)
            variants_array = utils.get_product_variants_array(product)
            product_url = utils.get_product_url(product, current_site)
            if image_array and variants_array and product_url:
                self.client.ecommerce.add_store_product(
                    self.store_id,
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
        except ApiClientError as error:
            logger.error("Error: {}".format(error.text))

    def customer_created(self, customer: "User", previous_value: Any) -> Any:
        self.client.lists.add_list_member(
            self.list_id,
            {
                "email_address": customer.email.__str__(),
                "status": "subscribed"
            }
        )

    def checkout_created(self, checkout: "Checkout", previous_value: Any) -> Any:
        user = self.get_or_create_user(checkout)
        if user:
            try:
                response = self.client.ecommerce.add_store_cart(
                    self.store_id,
                    {
                        "id": checkout.id,
                        "currency_code": "eur",
                        "customer": user,
                        "checkout_url": checkout.redirect_url,
                        "order_total": calculations.checkout_total(
                            checkout=checkout,
                            lines=checkout.lines
                        ),
                        "lines": utils.get_checkout_lines(checkout),
                    }
                )
                checkout.private_metadata["mailchimp_cart_id"] = response.get("id")
            except ApiClientError as error:
                logger.error("Unable to create cart {}", error)

    def checkout_to_order(self, checkout: "Checkout", order: "Order",
                          previous_value: Any) -> Any:
        checkout_id = checkout.private_metadata.get("mailchimp_cart_id")
        order.private_metadata["mailchimp_cart_id"] = checkout_id
        order.save()

    def order_fully_paid(self, order: "Order", previous_value: Any) -> Any:
        try:
            self.client.ecommerce.delete_store_cart(
                self.store_id,
                order.private_metadata.get("mailchimp_cart_id")
            )
        except ApiClientError as error:
            logger.error("Unable to delete cart {}", error)

    def get_or_create_user(self, checkout: "CheckOut") -> {}:
        try:
            return self.client.ecommerce.get_store_customer(
                self.store_id,
                checkout.user.id
            )
        except ApiClientError:
            try:
                return self.client.ecommerce.add_store_customer(
                    self.store_id,
                    {
                        "id": checkout.user.id,
                        "email_address": checkout.get_customer_email(),
                        "opt_in_status": False
                    }
                )
            except ApiClientError:
                return None

    def checkout_updated(self, checkout: "CheckOut", previous_value: Any) -> Any:
        user = self.get_or_create_user(checkout)
        if user:
            try:
                self.client.ecommerce.update_store_cart(
                    self.store_id,
                    checkout.private_metadata.get("mailchimp_cart_id"),
                    {
                        "currency_code": "eur",
                        "customer": user,
                        "order_url": checkout.redirect_url,
                        "order_total": calculations.checkout_total(
                            checkout=checkout,
                            lines=checkout.lines
                        ),
                        "lines": utils.get_checkout_lines(checkout),
                    }
                )
            except ApiClientError as error:
                logger.error("Unable to create cart {}", error)

    def full_sync(self):
        self.client.ecommerce.delete_store(self.store_id)
        self.client.ecommerce.add_store(
            {
                "id": self.store_id,
                "list_id": self.list_id,
                "name": "TodaJoia Fitness Fashion",
                "currency_code": "EUR",
                "platform": "saleor",
                "email_address": "info@todajoia.com"
            }
        )
        for product in Product.objects.all():
            try:
                current_site = Site.objects.get_current()
                image_array = utils.get_product_images_array(product, current_site)
                variants_array = utils.get_product_variants_array(product)
                product_url = utils.get_product_url(product, current_site)
                if image_array and variants_array and product_url:
                    self.client.ecommerce.add_store_product(
                        self.store_id,
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
            except ApiClientError as error:
                logger.error("Error: {}".format(error.text))
