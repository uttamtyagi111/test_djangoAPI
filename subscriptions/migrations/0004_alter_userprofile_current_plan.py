# Generated by Django 5.1.2 on 2024-11-05 22:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_alter_plan_email_limit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='current_plan',
            field=models.ForeignKey(default='Trial', null=True, on_delete=django.db.models.deletion.SET_NULL, to='subscriptions.plan'),
        ),
    ]