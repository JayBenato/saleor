from xml.etree import ElementTree

from django.http import HttpResponse
import logging
from saleor.account.models import User
from saleor.plugins.danea.xml_converter import process_product_xml, \
    create_orders

logger = logging.getLogger(__name__)


def process(request, token: str):
    if auth(token):
        if request.method == 'POST':
            file = request.FILES.get('file')
            logger.info("Processing danea request...")
            discarted: [str] = process_product_xml(file)
            if len(discarted) > 0:
                return HttpResponse("Discarted products :" + discarted.__str__(),
                                    status=200)
            else:
                return HttpResponse("OK")
        if request.method == 'GET':
            file = create_orders()
            logger.info(ElementTree.tostring(file))
            return HttpResponse(ElementTree.tostring(file),
                                content_type='application/xml')
    else:
        return HttpResponse("Wrong user credentials", status=200)


def auth(request):
    logger.error(request)
    if User.objects.get(email='direzione@todajoia.it').check_password(request):
        logger.info("User authenticated on danea endpoint ")
        return True
    return False
