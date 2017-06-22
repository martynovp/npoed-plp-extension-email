# coding: utf-8

import base64
from django.core.urlresolvers import reverse
from django.template import Template, Context
from django.utils.translation import ugettext_lazy as _
from plp.notifications.base import MassSendEmails
from .models import SupportEmail


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
        self.email_to_user = dict([(i.email, i) for i in recipients])
        SupportEmail.objects.filter(id=self.obj.id).update(recipients_number=len(self.email_to_user))
        return self.email_to_user.keys()

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
            return self.add_unsubscribe_footer(email, html_msg=msg)
        return ''

    def get_context(self, email=None):
        return {
            'user': self.email_to_user[email],
        }

    def get_extra_headers(self, email=None):
        return {'List-Unsubscribe': self.get_unsubscribe_url(email)}

    def get_unsubscribe_url(self, email):
        username = self.email_to_user.get(email).username
        url = reverse('bulk-unsubscribe', kwargs={'hash_str': base64.b64encode(username)})
        return '{prefix}://{site}{url}'.format(url=url, **self.defaults)

    def add_unsubscribe_footer(self, email, plaintext_msg=None, html_msg=None):
        url = self.get_unsubscribe_url(email)
        if plaintext_msg:
            return _(u'{0}\n\nДля отписки от информационной рассылки команды платформы {1} перейдите '
                     u'по ссылке {2}'.format(plaintext_msg, self.defaults['PLATFORM_NAME'], url))
        if html_msg:
            return _(u'{0}<br/><p>Для отписки от информационной рассылки команды платформы {1} перейдите '
                     u'<a href="{2}">по ссылке</a></p>'.format(html_msg, self.defaults['PLATFORM_NAME'], url))
        return ''
