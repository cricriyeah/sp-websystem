from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('fleet', '0031_tarifa_a_servicio')]

    operations = [migrations.DeleteModel(name='Tarifa')]
