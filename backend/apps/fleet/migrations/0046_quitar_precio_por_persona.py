from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0045_normalizar_precio_paquete'),
    ]

    operations = [
        migrations.RemoveField(model_name='paquete', name='precio_por_persona'),
    ]
