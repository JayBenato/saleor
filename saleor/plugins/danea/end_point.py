from xml.etree import ElementTree

from django.http import HttpResponse
import logging
from saleor.plugins.danea.xml_converter import process_product_xml, \
    create_orders

logger = logging.getLogger(__name__)


def process(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        logger.info("Processing danea request...")
        discarted: [str] = process_product_xml(file)
        if len(discarted) > 0:
            return HttpResponse("Discarted products :" + discarted.__str__(), status=200)
        else:
            return HttpResponse("OK")
    if request.method == 'GET':
        file = create_orders()
        logger.info(ElementTree.tostring(file))
        return HttpResponse(ElementTree.tostring(file), content_type='application/xml')

def authenticate(request):
    logger.info('Authenticating request')
    username = request.POST['username']
    password = request.POST['password']
    # return authenticate(request, username=username, password=password)
