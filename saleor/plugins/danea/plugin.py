import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import pgettext_lazy
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.models import PluginConfiguration, DaneaOrder

logger = logging.getLogger(__name__)


class DaneaPlugin(BasePlugin):
    PLUGIN_NAME = "DaneaPlugin"
    PLUGIN_ID = "danea.integration"
    CONFIG_STRUCTURE = {
        "Username or account": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide user or account details"
            ),
            "label": pgettext_lazy("Plugin label", "Username or account"),
        },
        "Password or license": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide password or license details"
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

    def order_fully_paid(self, order: "Order", previous_value: Any) -> Any:
        DaneaOrder.objects.create(
            saleor_order_id=order.id
        )
        return previous_value
