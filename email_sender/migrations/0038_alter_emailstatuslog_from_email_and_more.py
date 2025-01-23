# Generated by Django 5.1.2 on 2025-01-20 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('email_sender', '0037_rename_email_list_campaign_contact_list'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailstatuslog',
            name='from_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='emailstatuslog',
            name='smtp_server',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
