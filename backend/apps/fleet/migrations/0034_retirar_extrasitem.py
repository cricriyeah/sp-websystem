from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0033_extrasitem_a_personalizacion'),
        ('bookings', '0046_retirar_reservaextra'),
    ]
    operations = [migrations.DeleteModel(name='ExtrasItem')]
