from dataclasses import dataclass

from saleor.graphql.core.scalars import Decimal


@dataclass(init=False, repr=True)
class DaneaVariant:
    size: str
    qty: int
    barcode: str
    original_size: str


@dataclass(init=False, repr=True)
class DaneaProduct:
    internal_id: str
    code: str
    original_name: str
    original_color: str
    rm_code: str
    type: str
    category: str
    material: str
    collection: str
    category: str
    name: str
    color: str
    gross_price: Decimal
    net_price: Decimal
    sale_price: Decimal
    r120_price: Decimal
    r110_price: Decimal
    r100_price: Decimal
    web_price: Decimal
    variants: []
