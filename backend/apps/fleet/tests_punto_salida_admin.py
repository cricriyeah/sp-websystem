"""El admin de Servicios hace visible a quien le falta el punto de encuentro.

El «Sales de» (`Servicio.punto_salida`) es el lugar que va en los correos de confirmacion
y de asignacion. Si esta vacio el correo dice que se confirma por WhatsApp, asi que al
jefe hay que avisarle en la lista de servicios cuales faltan.
"""
from django.urls import reverse

from apps.testing import EmpresaTestCase, crear_servicio_pesca


class PuntoDeSalidaEnElAdminTests(EmpresaTestCase):
    def setUp(self):
        self.client.force_login(self.crear_jefe())
        self.url = reverse('admin:fleet_servicio_changelist')

    def test_un_servicio_de_mar_sin_punto_se_marca_como_falta(self):
        crear_servicio_pesca(self.empresa)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'data-falta-punto')

    def test_un_servicio_con_punto_muestra_el_lugar_y_no_se_marca(self):
        crear_servicio_pesca(self.empresa, punto_salida='Muelle Norte')

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Muelle Norte')
        self.assertNotContains(respuesta, 'data-falta-punto')

    def test_un_hospedaje_sin_punto_no_se_marca(self):
        # Un hotel no tiene punto de encuentro: marcarlo seria ruido.
        crear_servicio_pesca(
            self.empresa, slug='hotel-adm', nombre='Hotel', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )

        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, 'data-falta-punto')

    def test_la_ayuda_del_campo_dice_que_va_en_los_correos(self):
        servicio = crear_servicio_pesca(self.empresa)

        respuesta = self.client.get(reverse('admin:fleet_servicio_change', args=[servicio.pk]))

        self.assertContains(respuesta, 'correos de confirmación y de asignación')
