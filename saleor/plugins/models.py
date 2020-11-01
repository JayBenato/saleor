from django.db import models
from django.db.models import JSONField  # type: ignore
from django.contrib.postgres.fields import ArrayField

from ..core.permissions import PluginsPermissions
from ..core.utils.json_serializer import CustomJsonEncoder


class PluginConfiguration(models.Model):
    identifier = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=False)
    configuration = JSONField(
        blank=True, null=True, default=dict, encoder=CustomJsonEncoder
    )

    class Meta:
        permissions = ((PluginsPermissions.MANAGE_PLUGINS.codename, "Manage plugins"),)

    def __str__(self):
        return f"Configuration of {self.name}, active: {self.active}"


class DaneaOrder(models.Model):
    saleor_order_id = models.CharField(max_length=250)

class DaneaConfiguration(models.Model):
    property = models.CharField(max_length=20)
    saleor_property = models.CharField(max_length=20)
    danea_property = ArrayField(models.CharField(max_length=20), blank=True)
