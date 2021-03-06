# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-01-25 08:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hero_advantages', '0002_auto_20171230_1528'),
    ]

    operations = [
        migrations.AddField(
            model_name='advantage',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='advantage',
            name='date_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='hero',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='hero',
            name='date_modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
