import logging
from typing import Any
from xml.etree.ElementTree import ElementTree

from django.core.exceptions import ValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.utils.translation import pgettext_lazy
from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.plugins.danea import tasks, utils
from saleor.plugins.models import PluginConfiguration, DaneaOrder

logger = logging.getLogger(__name__)


class DaneaPlugin(BasePlugin):
    PLUGIN_NAME = "DaneaPlugin"
    PLUGIN_ID = "todajoia.integration.danea"
    DEFAULT_CONFIGURATION = [
        {"name": "Password", "value": None},
        {"name": "Update Google Feeds", "value": True},
        {"name": "Latest Collection", "value": False},
        {"name": "Reprocess Products Attributes", "value": False},
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
        },
        "Reprocess Products Attributes": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Plugin will reprocess products attributes"
            ),
            "label": pgettext_lazy("Plugin label", "Reprocess products attributes"),
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
        if configuration["Reprocess Products Attributes"] is True:
            tasks.reprocess_products_attributes().delay()
            tasks.update_google_feeds_task.apply_async(countdown=800)
            for config in plugin_configuration.configuration:
                if config["name"] == "Reprocess Products Attributes":
                    config["value"] = False

    def order_created(self, order: "Order", previous_value: Any):
        DaneaOrder.objects.create(
            saleor_order_id=order.id
        )

    def webhook(self, request: WSGIRequest, path: str, previous_value) -> HttpResponse:
        configuration = {item["name"]: item["value"] for item in self.configuration}
        if path == configuration.get("Password"):
            if request.method == 'POST':
                file = request.FILES.get('file')
                discarted: [str] = utils.process_product_xml(file)
                if len(discarted) > 0:
                    return HttpResponse(
                        "Discarted products :" + discarted.__str__(),
                        status=200
                    )
                else:
                    return HttpResponse("OK")
            if request.method == 'GET':
                file = utils.create_orders()
                return HttpResponse(
                    ElementTree.tostring(file),
                    content_type='application/xml'
                )
        else:
            return HttpResponse("Wrong Password", status=200)
