import os

from django.db import migrations


def crear_sede_y_empresa(apps, schema_editor):
    Sede = apps.get_model('tenancy', 'Sede')
    Empresa = apps.get_model('tenancy', 'Empresa')

    sede = Sede.objects.create(
        nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan', activo=True,
    )
    Empresa.objects.create(
        sede=sede, nombre='Sal y Sol Sportfishing', slug='sal-y-sol',
        activo=True, exclusiva=True,
        # Backfill desde las mismas env vars que hoy lee settings.py global --
        # sin esto, entre que migrate termina y que alguien teclea las llaves a
        # mano en el admin, el checkout queda en 503 (ver Revision 4, N15).
        stripe_secret_key=os.environ.get('STRIPE_SECRET_KEY', ''),
        stripe_webhook_secret=os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
        stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    )


def eliminar(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Sede = apps.get_model('tenancy', 'Sede')
    Empresa.objects.filter(slug='sal-y-sol').delete()
    Sede.objects.filter(slug='la-paz').delete()


class Migration(migrations.Migration):

    dependencies = [('tenancy', '0001_initial')]

    operations = [migrations.RunPython(crear_sede_y_empresa, eliminar)]
