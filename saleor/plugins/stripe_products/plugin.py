from django.utils.translation import pgettext_lazy
from typing import Any
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.stripe_products import tasks


class StripeProducts(BasePlugin):
    PLUGIN_NAME = "StripeProducts"
    PLUGIN_ID = "todajoia.integration.stripe"
    DEFAULT_CONFIGURATION = [
        {"name": "Public API key", "value": None},
        {"name": "Secret API key", "value": None},
        {"name": "Process Products", "value": False},
    ]
    CONFIG_STRUCTURE = {
        "Public API key": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "Provide Stripe public API key.",
            "label": "Public API key",
        },
        "Secret API key": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "Provide Stripe secret API key.",
            "label": "Secret API key",
        },
        "Process Products": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Plugin will update google feeds at every product update"
            ),
            "label": pgettext_lazy("Plugin label", "Update Google Feeds"),
        }
    }
    def product_created(self, product: "Product", previous_value: Any) -> Any:
        tasks.stripe_create_product.delay(
            product.id,
            {item["name"]: item["value"] for item in self.configuration}
        )

    def product_updated(self, product: "Product", previous_value: Any) -> Any:
        tasks.stripe_create_or_update_product.delay(
            product.id,
            {item["name"]: item["value"] for item in self.configuration}
        )

    @classmethod
    def validate_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        configuration = {item["name"]: item["value"] for item in plugin_configuration.configuration}
        if configuration["Process Products"] is True:
            tasks.stripe_full_products_sync.delay(configuration)
            for config in plugin_configuration.configuration:
                if config["name"] == "Process Products":
                    config["value"] = False
