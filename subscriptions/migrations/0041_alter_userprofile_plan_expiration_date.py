# Generated by Django 5.1.2 on 2025-01-05 00:32

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0040_alter_userprofile_plan_expiration_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='plan_expiration_date',
            field=models.DateTimeField(default=datetime.datetime(2025, 2, 4, 0, 31, 43, 54289, tzinfo=datetime.timezone.utc)),
        ),
    ]
