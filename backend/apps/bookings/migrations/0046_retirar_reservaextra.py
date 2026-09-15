from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0045_rename_reservapersonalizacion'),
        ('fleet', '0033_extrasitem_a_personalizacion'),
    ]
    operations = [
        migrations.DeleteModel(name='ReservaExtra'),
        migrations.AlterField('reserva', 'servicio', models.ForeignKey(
            'fleet.Servicio', on_delete=django.db.models.deletion.PROTECT,
            null=True, blank=True, related_name='reservas',
            help_text='Servicio o experiencia que ampara esta reserva. Vacío solo cuando hay paquete.',
        )),
    ]
