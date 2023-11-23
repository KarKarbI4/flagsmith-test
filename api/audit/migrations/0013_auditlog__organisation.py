# Generated by Django 3.2.20 on 2023-10-13 12:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organisations', '0046_allow_allowed_projects_to_be_null'),
        ('audit', '0012_auto_20230517_1006'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='_organisation',
            field=models.ForeignKey(db_column='organisation', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='audit_logs', to='organisations.organisation'),
        ),
    ]