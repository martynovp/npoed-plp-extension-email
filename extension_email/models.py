# coding: utf-8

from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from plp.models import User


class SupportEmail(models.Model):
    """
    Модель для сохранения информации и настроек массовой рассылки
    """
    sender = models.ForeignKey(User, verbose_name=_(u'Отправитель'))
    target = JSONField(blank=True, null=True)
    subject = models.CharField(max_length=128, blank=True, verbose_name=_(u'Тема'))
    html_message = models.TextField(null=True, blank=True, verbose_name=_(u'HTML письма'))
    text_message = models.TextField(null=True, blank=True, verbose_name=_(u'Текст письма'))
    confirmed = models.BooleanField(verbose_name=_(u'Отправка подтверждена'), default=True)
    recipients_number = models.IntegerField(verbose_name=_(u'Количество получателей'), default=None, null=True)
    to_myself = models.BooleanField(default=False, verbose_name=_(u'Сообщение только себе'))
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _(u'Рассылка')
        verbose_name_plural = _(u'Рассылки')

    def __unicode__(self):
        return '%s - %s' % (self.sender, self.subject)

    def get_recipients(self):
        from .utils import filter_users
        if self.target:
            return filter_users(self)[0]
        return []


class BulkEmailOptout(models.Model):
    user = models.ForeignKey(User, verbose_name=_(u'Пользователь'), related_name='bulk_email_optout')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name=_(u'Когда пользователь отписался от рассылки'))

    class Meta:
        verbose_name = _(u'Отписка от рассылок')
        verbose_name_plural = _(u'Отписки от рассылок')


class SupportEmailTemplate(models.Model):
    slug = models.CharField(max_length=128, verbose_name=_(u'Название шаблона'), unique=True)
    subject = models.CharField(max_length=128, verbose_name=_(u'Тема'))
    html_message = models.TextField(verbose_name=_(u'HTML письма'))
    text_message = models.TextField(null=True, blank=True, verbose_name=_(u'Текст письма'))

    def __unicode__(self):
        return self.slug

    class Meta:
        verbose_name = _(u'Шаблон рассылки')
        verbose_name_plural = _(u'Шаблоны рассылок')
