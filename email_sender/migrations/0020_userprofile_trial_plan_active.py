# Generated by Django 5.1.2 on 2024-10-23 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('email_sender', '0019_remove_plan_max_emails_remove_plan_validity_days_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='trial_plan_active',
            field=models.BooleanField(default=False),
        ),
    ]
