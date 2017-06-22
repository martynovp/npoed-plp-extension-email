# coding: utf-8

from django.contrib import admin
from autocomplete_light import modelform_factory
from .models import SupportEmail, BulkEmailOptout, SupportEmailTemplate


@admin.register(SupportEmail)
class SupportEmailAdmin(admin.ModelAdmin):
    list_display = ('sender', 'subject', 'created', 'confirmed')
    form = modelform_factory(SupportEmail, exclude=[])


@admin.register(BulkEmailOptout)
class BulkEmailOptoutAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    form = modelform_factory(BulkEmailOptout, exclude=[])


@admin.register(SupportEmailTemplate)
class SupportEmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('slug', 'subject', )
