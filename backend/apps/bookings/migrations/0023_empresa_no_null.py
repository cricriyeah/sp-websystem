import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0022_backfill_empresa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reserva', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='reservas', to='tenancy.empresa',
            ),
        ),
        migrations.AlterField(
            model_name='cupodiario', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='cupos_diarios', to='tenancy.empresa',
            ),
        ),
        migrations.AlterField(
            model_name='vendedora', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='vendedoras', to='tenancy.empresa',
            ),
        ),
    ]
