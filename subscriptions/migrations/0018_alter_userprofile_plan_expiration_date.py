# Generated by Django 5.1.2 on 2024-12-27 17:49

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0017_alter_userprofile_plan_expiration_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='plan_expiration_date',
            field=models.DateTimeField(default=datetime.datetime(2025, 1, 26, 17, 49, 33, 462877, tzinfo=datetime.timezone.utc)),
        ),
    ]