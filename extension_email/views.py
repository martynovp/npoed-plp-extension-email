# coding: utf-8

import base64
from django.conf import settings
from django.core.urlresolvers import reverse_lazy
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.utils import timezone
from django.utils.translation import ugettext as _, ungettext
from django.views.decorators.http import require_POST
from django.views.generic import CreateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from api.views.user import ApiKeyPermission
from plp.models import User
from .forms import BulkEmailForm
from .models import BulkEmailOptout, SupportEmailTemplate, SupportEmail
from .tasks import support_mass_send
from .utils import filter_users


class FromSupportView(CreateView):
    """
    Вьюха для создания и отправки массовых рассылок
    """
    form_class = BulkEmailForm
    success_url = reverse_lazy('frontpage')
    template_name = 'extension_email/main.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_staff:
            return super(FromSupportView, self).dispatch(request, *args, **kwargs)
        raise Http404

    def get_template_names(self):
        if getattr(settings, 'EXTENSION_EMAIL_OPENEDU_TEMPLATE', True):
            return [self.template_name]
        return ['extension_email/main_miptx.html']

    def form_valid(self, form):
        item = form.save(commit=False)
        item.sender = self.request.user
        item.target = form.to_json()
        item.confirmed = False
        users, msg_type = filter_users(item)
        error = False
        if msg_type == 'to_myself':
            msg = _(u'Вы уверены, что хотите отправить это сообщение себе?')
            item.to_myself = True
        elif msg_type == 'to_all':
            msg = _(u'Вы хотите отправить письмо с темой "%(theme)s" всем пользователям. Продолжить?') % \
                  {'theme': item.subject}
        elif msg_type == 'error':
            msg = _(u'Ошибка коммуникации с EDX')
            error = True
        else:
            msg = ungettext(
                u'Вы хотите отправить письмо с темой "%(theme)s" %(user_count)s пользователю. Продолжить?',
                u'Вы хотите отправить письмо с темой "%(theme)s" %(user_count)s пользователям. Продолжить?',
                users.count()
            ) % {'theme': item.subject, 'user_count': users.count()}
        if not error and msg_type != 'to_myself':
            now = timezone.now()
            existing = SupportEmail.objects.filter(
                subject=item.subject,
                confirmed=True,
                to_myself=False,
                modified__gt=now - timezone.timedelta(hours=24)
            ).order_by('-created').first()
            if existing:
                user_count = existing.recipients_number or 0
                delta = now - existing.modified
                hours_ago = delta.seconds / 3600
                minutes_ago = (delta - hours_ago * timezone.timedelta(hours=1)).seconds / 60
                msg = ungettext(
                    u'Письмо с темой "{subject}" было отправлено пользователем {user} {user_count} пользователю '
                    u'{hours_ago} {minutes_ago} назад. Хотите отправить еще раз?',
                    u'Письмо с темой "{subject}" было отправлено пользователем {user} {user_count} пользователям '
                    u'{hours_ago} {minutes_ago} назад. Хотите отправить еще раз?',
                    user_count).format(**{
                        'subject': item.subject,
                        'user': existing.sender.username,
                        'user_count': user_count,
                        'hours_ago': ungettext(u'{counter} час', u'{counter} часов', hours_ago).format(counter=hours_ago),
                        'minutes_ago': ungettext(u'{counter} минуту', u'{counter} минут', minutes_ago).format(counter=minutes_ago)
                    })
        if not error:
            item.save()
        return JsonResponse({
            'item_id': item.id,
            'valid': True,
            'message': msg,
            'error': error,
        })

    def form_invalid(self, form):
        form_html = get_template('extension_email/_message_form.html').render(
            context={'form': form}, request=self.request
        )
        return JsonResponse({'form': form_html, 'valid': False})


@require_POST
def confirm_sending(request):
    if not request.user.is_staff:
        raise Http404
    try:
        item = SupportEmail.objects.get(id=request.POST.get('item_id'))
        assert item.sender == request.user
        assert not item.confirmed
    except (SupportEmail.DoesNotExist, ValueError, AssertionError) as e:
        return JsonResponse({'status': 1}, status=status.HTTP_400_BAD_REQUEST)
    item.confirmed = True
    item.save()
    support_mass_send.delay(item.id)
    return JsonResponse({'status': 0})


def unsubscribe(request, hash_str):
    """
    отписка от рассылок по уникальному для пользователя хэшу
    """
    try:
        s = base64.b64decode(hash_str)
    except TypeError:
        raise Http404
    try:
        user = User.objects.get(username=s)
    except User.DoesNotExist:
        raise Http404
    BulkEmailOptout.objects.get_or_create(user=user)
    context = {
        'profile_url': '{}/profile/'.format(settings.SSO_NPOED_URL),
    }
    return render(request, 'extension_email/unsubscribed.html', context)


def support_mail_template(request):
    """
    возвращает текст шаблона массовой рассылки
    """
    if not request.user.is_staff:
        raise Http404
    try:
        template = SupportEmailTemplate.objects.get(id=request.POST.get('id'))
    except (SupportEmailTemplate.DoesNotExist, ValueError):
        raise Http404
    return JsonResponse({
        'subject': template.subject,
        'text_message': template.text_message,
        'html_message': template.html_message,
    })


class OptoutStatusView(APIView):
    """
        **Описание**

            Ручка для проверки и изменения статуса подписки пользователя на информационные
            рассылки платформы. Требуется заголовок X-PLP-Api-Key.

        **Пример запроса**

            GET bulk_email/api/optout_status/?user=<username>

            POST bulk_email/api/optout_status/{
                "user" : username,
                 "status" : boolean
            }

        **Параметры post-запроса**

            * user: логин пользователя
            * status: True/False для активации/деактивации подписки соответственно

        **Пример ответа**

            * {
                  "status": True
              }

            новый статус подписки

            404 если пользователь не найден
            400 если переданы не все параметры

    """
    permission_classes = (ApiKeyPermission,)

    def get(self, request, *args, **kwargs):
        username = request.query_params.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        optout = BulkEmailOptout.objects.filter(user=user).first()
        if optout:
            return Response({'status': False})
        else:
            return Response({'status': True})

    def post(self, request, *args, **kwargs):
        username = request.data.get('user')
        new_status = request.data.get('status')
        if isinstance(new_status, basestring):
            new_status = new_status.lower() != 'false'
        if not username or new_status is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        old_status = not BulkEmailOptout.objects.filter(user=user).exists()
        if new_status == old_status:
            return Response({'status': new_status})
        if new_status:
            BulkEmailOptout.objects.filter(user=user).delete()
        else:
            BulkEmailOptout.objects.create(user=user)
        return Response({'status': new_status})
