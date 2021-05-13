from django import template
from ..models import OrderLine, Order
register = template.Library()


@register.simple_tag()
def display_translated_order_line_name(order_line: OrderLine):
    product_name = order_line.translated_product_name or order_line.product_name
    variant_name = order_line.translated_variant_name or order_line.variant_name
    return f"{product_name} ({variant_name})" if variant_name else product_name


@register.simple_tag()
def get_payment_method_from_order(order: Order):
    gateway = order.get_last_payment().gateway.__str__()
    payment = None
    if gateway == 'todajoia.payments.OnDeliveryPayment':
        payment = "Contrassegno"
    if gateway == 'mirumee.payments.braintree':
        payment = "Braintree"
    if gateway == 'mirumee.payments.stripe':
        payment = "Stripe"
    if payment is None:
        return order.get_last_payment().__str__()
    else:
        return payment
