# coding: utf-8

import logging
from django.utils.timezone import now
from celery import task
from .models import SupportEmail
from .notifications import BulkEmailSend


@task
def support_mass_send(obj_id):
    logging.info('%s Started sending bulk emails' % now().strftime('%H:%M:%S %d.%m.%Y'))
    obj = SupportEmail.objects.get(id=obj_id)
    msgs = BulkEmailSend(obj)
    msgs.send()
    logging.info('%s Ended sending bulk emails' % now().strftime('%H:%M:%S %d.%m.%Y'))
