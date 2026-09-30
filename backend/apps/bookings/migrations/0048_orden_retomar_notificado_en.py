from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('bookings', '0047_reserva_paquete_estancia')]

    operations = [
        migrations.AddField(
            model_name='orden',
            name='retomar_notificado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
