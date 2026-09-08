from django.db import migrations
from django.utils import timezone

def backfill_existing_officers(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(role='MUNICIPALITY_OFFICER').update(
        verification_status='APPROVED',
        verified_at=timezone.now()
    )

def reverse_backfill(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_customuser_rejection_reason_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_existing_officers, reverse_backfill),
    ]
