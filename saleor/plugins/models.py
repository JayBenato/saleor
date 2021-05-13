from django.db import models
from django.db.models import JSONField  # type: ignore

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


class DaneaCategoryMappings(models.Model):
    danea_field = models.CharField(max_length=250)
    saleor_category_slug = models.CharField(max_length=250)
    saleor_type_slug = models.CharField(max_length=250)


class DaneaAttributeMappings(models.Model):
    danea_field = models.CharField(max_length=250, unique=True)
    saleor_attribute_slug = models.CharField(max_length=250, unique=True)


class DaneaAttributeValuesMappings(models.Model):
    attribute_type = models.CharField(max_length=128, default="")
    danea_field = models.CharField(max_length=250, unique=True)
    saleor_attribute_value_slug = models.CharField(max_length=250)


class DaneaCollectionsMappings(models.Model):
    keyword = models.CharField(max_length=128)
    saleor_collection_slug = models.CharField(max_length=128)
