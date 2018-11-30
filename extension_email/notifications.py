# coding: utf-8

import base64
import logging
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives
from django.utils.functional import cached_property
from django.db import models, transaction
from django.template import Template, Context
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from post_office.mail import send
from tp_massmail.base import MassSendEmails
from plp.models import User
from plp.utils.helpers import get_prefix_and_site
from .models import EmailRelated, SupportEmail, SupportEmailStatus


def send_queued():
    BATCH_SIZE = getattr(settings, 'EMAIL_BATCH_SIZE', 5000)
    objects = SupportEmailStatus.objects.filter(status=SupportEmailStatus.STATUS_QUEUED)[:BATCH_SIZE]
    connection = get_connection()
    connection.open()
    for obj in objects:
        success = SupportEmailSender(obj, connection).send()
        if success:
            obj.status = SupportEmailStatus.STATUS_SENT
            SupportEmail.objects.filter(id=obj.support_email_id).update(
                delivered_number=models.F('delivered_number') + 1)
        else:
            obj.status = SupportEmailStatus.STATUS_FAILED
        obj.save()
    connection.close()


class SupportEmailSender(object):
    """
    Класс для генерации и отправки письма по данным объекта SupportEmailStatus
    """
    def __init__(self, obj, connection):
        self.obj = obj
        self.connection = connection

    def get_subject(self):
        return self.obj.support_email.subject

    def get_text(self):
        if self.obj.support_email.text_message:
            t = Template(self.obj.support_email.text_message)
            msg = t.render(Context(self.context))
            return self.add_unsubscribe_footer(plaintext_msg=msg)
        return ''

    def get_html(self):
        if self.obj.support_email.html_message:
            t = Template(self.obj.support_email.html_message)
            msg = t.render(Context(self.context))
            return self.add_unsubscribe_footer(html_msg=msg)
        return ''

    @cached_property
    def context(self):
        ctx = {
            'user': User.objects.filter(email=self.obj.email).first(),
        }
        ctx.update(get_prefix_and_site())
        return ctx

    def get_extra_headers(self):
        return {'List-Unsubscribe': self.get_unsubscribe_url(self.obj.email)}

    def send(self):
        msg = EmailMultiAlternatives(
            self.get_subject() or '',
            self.get_text() or '',
            settings.EMAIL_NOTIFICATIONS_FROM,
            [self.obj.email],
            connection=self.connection,
            headers=self.get_extra_headers(),
        )
        html = self.get_html()
        if html:
            msg.attach_alternative(html, 'text/html')
        try:
            msg.send()
            return True
        except Exception as e:
            logging.exception(e)
            return False

    def get_unsubscribe_url(self, email):
        url = '{}?id={}'.format(
            reverse('bulk-unsubscribe-v2', kwargs={'hash_str': base64.b64encode(email.encode('utf8'))}),
            str(self.obj.support_email_id)
        )
        return '{prefix}://{site}{url}'.format(url=url, **self.context)

    def add_unsubscribe_footer(self, plaintext_msg=None, html_msg=None):
        url = self.get_unsubscribe_url(self.obj.email)
        if plaintext_msg:
            return _('{0}\n\nДля отписки от информационной рассылки перейдите '
                     'по ссылке {1}'.format(plaintext_msg, url))
        if html_msg:
            return _('{0}<br/><p>Для отписки от информационной рассылки перейдите '
                     '<a href="{1}">по ссылке</a></p>'.format(html_msg, url))
        return ''


class BulkEmailSend(MassSendEmails):
    """
    Расширение класса MassSendEmails для работы с объектами SupportEmail
    (тексты и заголовки писем берутся из них, а не из шаблонов),
    а также добавления футера с отпиской от рассылок
    """
    def __init__(self, obj):
        self.obj = obj
        self.email_to_user = {}
        super(BulkEmailSend, self).__init__()

    def get_emails(self):
        recipients = self.obj.get_recipients()
        users = {i.email: i for i in User.objects.filter(email__in=recipients)}
        self.email_to_user = dict([(i, users.get(i)) for i in recipients])
        SupportEmail.objects.filter(id=self.obj.id).update(recipients_number=len(recipients))
        return recipients

    def get_subject(self, email=None):
        return self.obj.subject

    def get_text(self, email=None):
        if self.obj.text_message:
            t = Template(self.obj.text_message)
            msg = t.render(Context(self.get_context(email)))
            return self.add_unsubscribe_footer(email, plaintext_msg=msg)
        return ''

    def get_html(self, email=None):
        if self.obj.html_message:
            t = Template(self.obj.html_message)
            msg = t.render(Context(self.get_context(email)))
            return str(self.add_unsubscribe_footer(email, html_msg=msg))
        return ''

    def get_context(self, email=None):
        return {
            'user': self.email_to_user[email],
        }

    def get_extra_headers(self, email=None):
        return {'List-Unsubscribe': self.get_unsubscribe_url(email)}

    def send(self):
        with transaction.atomic():
            for msgs in self.generate_messages():
                for email in msgs:
                    item = send(commit=False, **email)
                    EmailRelated.create_from_parent_model(item, self.obj.id, commit=True)

    def get_unsubscribe_url(self, email):
        url = '{}?id={}'.format(
            reverse('bulk-unsubscribe-v2', kwargs={'hash_str': base64.b64encode(email.encode('utf8')).decode('utf8')}),
            str(self.obj.id)
        )
        return '{prefix}://{site}{url}'.format(url=url, **self.defaults)

    def add_unsubscribe_footer(self, email, plaintext_msg=None, html_msg=None):
        url = self.get_unsubscribe_url(email)
        if plaintext_msg:
            return _('{0}\n\nДля отписки от информационной рассылки перейдите '
                     'по ссылке {1}'.format(plaintext_msg, url))
        if html_msg:
            return _('{0}<br/><p>Для отписки от информационной рассылки перейдите '
                     '<a href="{1}">по ссылке</a></p>'.format(html_msg, url))
        return ''
