import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import pgettext_lazy
import mailchimp_marketing as  MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.models import PluginConfiguration
from saleor.product.models import Product

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert to dict to easier take config elements
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.client.set_config({
            "api_key": configuration["API Key"],
            "server": configuration["Server Prefix"]
        })
        self._cached_taxes = {}

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

    def mailchimp_product_created(self, product: "Product", previous_value: Any) -> Any:


    @staticmethod
    def mailchimp_get_product_variants_array(product: "Product") -> []:
        variants = []
        for variant in product.variants:
            variants.append(
                {"id": variant.id, "title": variant.name}
            )

    def mailchimp_update_product(self,mailchimp_product,configurations):
        saleor_product : Product = Product.objects.get(mailchimp_product.id)
        response = client.ecommerce.update_store_product(configurations["Store ID"], , {})


    def mailchimp_create_product(self, product:Product,configuration):
        # Convert to dict to easier take config elements
        configuration = {item["name"]: item["value"] for item in self.configuration}
        try:
            response = self.client.ecommerce.add_store_product(
                configuration["Store ID"],
                {
                    "id": product.id,
                    "title": product.name,
                    "variants": self.mailchimp_get_product_variants_array(product)
                }
            )
            print(response)
        except ApiClientError as error:
            print("Error: {}".format(error.text))

    def mailchimp_sync_products(self, products):
        configuration = {item["name"]: item["value"] for item in self.configuration}
        try:
            response = self.client.ecommerce.get_all_store_products(configuration["Store ID"])
            for saleor_product in Product.objects.all():

                    mailchimp_update_product(mailchimp_product,configuration)
                else:
                    mailchimp_create_product(mailchimp_product)
        except ApiClientError as error:
            print("Error: {}".format(error.text))
