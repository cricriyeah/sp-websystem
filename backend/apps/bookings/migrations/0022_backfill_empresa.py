from django.db import migrations


def backfill_empresa(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Reserva = apps.get_model('bookings', 'Reserva')
    CupoDiario = apps.get_model('bookings', 'CupoDiario')
    Vendedora = apps.get_model('bookings', 'Vendedora')

    empresa = Empresa.objects.get(slug='sal-y-sol')
    Reserva.objects.filter(empresa__isnull=True).update(empresa=empresa)
    CupoDiario.objects.filter(empresa__isnull=True).update(empresa=empresa)
    Vendedora.objects.filter(empresa__isnull=True).update(empresa=empresa)


def revertir(apps, schema_editor):
    Reserva = apps.get_model('bookings', 'Reserva')
    CupoDiario = apps.get_model('bookings', 'CupoDiario')
    Vendedora = apps.get_model('bookings', 'Vendedora')
    Reserva.objects.update(empresa=None)
    CupoDiario.objects.update(empresa=None)
    Vendedora.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
        ('bookings', '0021_empresa_nullable'),
    ]

    operations = [
        migrations.RunPython(backfill_empresa, revertir),
    ]
