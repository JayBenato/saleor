import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import pgettext_lazy
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.models import PluginConfiguration, DaneaOrder

logger = logging.getLogger(__name__)


class DaneaPlugin(BasePlugin):
    PLUGIN_NAME = "DaneaPlugin"
    PLUGIN_ID = "todajoia.integration.danea"
    DEFAULT_CONFIGURATION = [
        {"name": "Update Google Feeds", "value": True},
        {"name": "Password", "value": None},
    ]
    CONFIG_STRUCTURE = {
        "Update Google Feeds": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Plugin will update google feeds at every product update"
            ),
            "label": pgettext_lazy("Plugin label", "Update Google Feeds"),
        },
        "Password": {
            "type": ConfigurationTypeField.PASSWORD,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Provide password or license that validates end-point"
            ),
            "label": pgettext_lazy("Plugin label", "Password or license"),
        }
    }

    @classmethod
    def validate_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        """Validate if provided configuration is correct."""
        missing_fields = []
        configuration = plugin_configuration.configuration
        configuration = {item["name"]: item["value"] for item in configuration}
        if not configuration["Password"]:
            missing_fields.append("Password")

        if plugin_configuration.active and missing_fields:
            error_msg = (
                "To enable a plugin, you need to provide values for the "
                "following fields: "
            )
            raise ValidationError(error_msg + ", ".join(missing_fields))

    def order_created(self, order: "Order", previous_value: Any):
        DaneaOrder.objects.create(
            saleor_order_id=order.id
        )
        return previous_value
