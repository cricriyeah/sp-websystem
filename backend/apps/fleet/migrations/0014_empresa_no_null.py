import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0013_backfill_empresa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tarifa', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tarifa', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='extrasitem', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='extras_items', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='transporteprecio', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='precios_transporte', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='puntoencuentro', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='puntos_encuentro', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='codigopromocional', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='codigos_promocionales', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='embarcacion', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='capitan', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='capitanes', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='embarcacionnodisponible', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones_no_disponibles', to='tenancy.empresa'),
        ),
    ]
