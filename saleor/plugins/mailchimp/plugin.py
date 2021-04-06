import logging
from datetime import timezone
from typing import Any, List
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.utils.encoding import smart_text
from django.utils.translation import pgettext_lazy
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError
from saleor.core.taxes import charge_taxes_on_shipping
from saleor.discount.utils import fetch_discounts
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.mailchimp import utils
from saleor.plugins.models import PluginConfiguration
from saleor.product.models import Product, Attribute, Category, AttributeValue

logger = logging.getLogger(__name__)


class MailChimpPlugin(BasePlugin):
    PLUGIN_NAME = "MailChimpPlugin"
    PLUGIN_ID = "todajoia.integration.danea"
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
            "label": pgettext_lazy("Plugin label", "Password or license"),
        },
        "Store ID": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide your mail chimp server prefix"
            ),
            "label": pgettext_lazy("Plugin label", "Password or license"),
        }
    }
    client = MailchimpMarketing.Client()
    config = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert to dict to easier take config elements
        self.config = {item["name"]: item["value"] for item in self.configuration}
        self.client.set_config({
            "api_key": self.config["API Key"],
            "server": self.config["Server Prefix"]
        })

    @classmethod
    def validate_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        """Validate if provided configuration is correct."""
        missing_fields = []
        configuration = plugin_configuration.configuration
        configuration = {item["name"]: item["value"] for item in configuration}
        if not configuration["Username or account"]:
            missing_fields.append("Username or account")
        if not configuration["Password or license"]:
            missing_fields.append("Password or license")

        if plugin_configuration.active and missing_fields:
            error_msg = (
                "To enable a plugin, you need to provide values for the "
                "following fields: "
            )
            raise ValidationError(error_msg + ", ".join(missing_fields))

    @classmethod
    def _get_default_configuration(cls):
        defaults = {
            "name": cls.PLUGIN_NAME,
            "description": "",
            "active": True,
            "configuration": [
                {
                    "name": "Username or account",
                    "value": "",
                },
                {
                    "name": "Password or license",
                    "value": "",
                },
            ]
        }
        return defaults

    def product_updated(self, product: "Product", previous_value: Any) -> Any:
        # TODO make this a celery task
        return super().product_updated(product, previous_value)

    def product_created(self, product: "Product", previous_value: Any) -> Any:
        # TODO make this a celery task
        try:
            response = self.client.ecommerce.add_store_product(
                self.config["Store ID"],
                {
                    "id": product.id,
                    "url": self.mailchimp_get_product_url(product),
                    "title": product.name,
                    "type": product.product_type.name,
                    "image_url": "",
                    "images": self.mailchimp_get_product_images_url(product),
                    "variants": self.mailchimp_get_product_variants_array(product)
                }
            )
            print(response)
        except ApiClientError as error:
            print("Error: {}".format(error.text))

        return super().product_created(product, previous_value)

    def order_created(self, order: "Order", previous_value: Any):
        return super().order_created(order, previous_value)

    def order_fully_paid(self, order: "Order", previous_value: Any) -> Any:
        return super().order_fully_paid(order, previous_value)

    def order_updated(self, order: "Order", previous_value: Any) -> Any:
        return super().order_updated(order, previous_value)

    def preprocess_order_creation(self, checkout: "Checkout",
                                  discounts: List["DiscountInfo"], previous_value: Any):
        return super().preprocess_order_creation(checkout, discounts, previous_value)

    def order_cancelled(self, order: "Order", previous_value: Any) -> Any:
        return super().order_cancelled(order, previous_value)

    def order_fulfilled(self, order: "Order", previous_value: Any) -> Any:
        return super().order_fulfilled(order, previous_value)
