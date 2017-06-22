# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('extension_email', '0004_supportemailtemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportemail',
            name='confirmed',
            field=models.BooleanField(default=True, verbose_name='\u041e\u0442\u043f\u0440\u0430\u0432\u043a\u0430 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430'),
        ),
        migrations.AddField(
            model_name='supportemail',
            name='recipients_number',
            field=models.IntegerField(default=None, null=True, verbose_name='\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u0435\u0439'),
        ),
        migrations.AddField(
            model_name='supportemail',
            name='to_myself',
            field=models.BooleanField(default=False, verbose_name='\u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0442\u043e\u043b\u044c\u043a\u043e \u0441\u0435\u0431\u0435'),
        ),
    ]
