# Generated by Django 2.2.2 on 2020-12-09 17:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('TruckShare', '0007_auto_20201209_2239'),
    ]

    operations = [
        migrations.AddField(
            model_name='truck',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ownedTrucks', to=settings.AUTH_USER_MODEL),
        ),
    ]
