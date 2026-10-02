"""Siembra el catálogo operativo real en LOCAL: empresas, servicios y recursos.

NO usar en producción (pone llaves de Stripe placeholder). Idempotente.

Estructura de negocio:
  La Paz       -> Sal y Sol Sportfishing (pesca deportiva)
                  DLS Transporte (traslados; el slug se queda `transporte-la-paz`
                  porque el webhook de Stripe y el frontend dependen de él)
                  Paquete cruza-empresa Pesca + Traslado (lo siembra seed_local_demo)
  La Ventana   -> La Ventana Travel (pesca con mosca, avistamiento de ballenas y orcas)
  Puerto Chale -> Piratas Adventures (safari marino, avistamiento de ballenas, pesca)

Los precios y la flota de La Ventana y Puerto Chale son PLACEHOLDER (los reales no
se han pasado): las lanchas se llaman "DEMO ..." para que se vean en el admin y se
reemplacen. Los paquetes de La Ventana (precio por persona, mar en varios días) sí se siembran.

`--limpiar-demo` borra lo que dejó seed_local_demo y no es real (Hotel Malecón, paseo,
cabañas, snorkel, paquetes demo, TODAS las reservas y órdenes de prueba) y convierte la
empresa demo Tours Cabo en La Ventana Travel. Hazlo una sola vez, antes de sembrar.

Uso:  venv/Scripts/python.exe manage.py seed_catalogo_real [--limpiar-demo]
"""
from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede

LLAVES_PLACEHOLDER = dict(
    stripe_secret_key='sk_test_CAMBIAME',
    stripe_publishable_key='pk_test_CAMBIAME',
    stripe_webhook_secret='whsec_CAMBIAME',
)

# slug -> (nombre, sede)
EMPRESAS_REALES = {
    'sal-y-sol': ('Sal y Sol Sportfishing', 'la-paz'),
    'transporte-la-paz': ('DLS Transporte', 'la-paz'),
    'la-ventana-travel': ('La Ventana Travel', 'la-ventana'),
    'piratas-adventures': ('Piratas Adventures', 'puerto-chale'),
}

# (empresa, slug, nombre, tipo, estrategia_precio, precio, precio_usd, personas_incluidas,
#  capacidad_maxima, descripcion, [(recurso, capacidad)])
SERVICIOS = [
    ('la-ventana-travel', 'pesca-con-mosca', 'Pesca con mosca', 'pesca', 'por_grupo',
     '6000', '350', 2, 3, 'Pesca con mosca (fly fishing) en La Ventana.',
     [('DEMO Panga La Ventana 1', 3), ('DEMO Panga La Ventana 2', 3)]),
    ('la-ventana-travel', 'avistamiento-ballenas-orcas', 'Avistamiento de ballenas y orcas', 'paseo',
     'por_persona', '1200', '70', 1, 12,
     'Salida al mar para ver ballenas y orcas según la temporada; la logística es la misma.',
     [('DEMO Lancha La Ventana 1', 12), ('DEMO Lancha La Ventana 2', 12)]),
    ('piratas-adventures', 'safari-marino', 'Safari marino', 'paseo', 'por_persona', '900', '55', 1, 10,
     'Safari marino en Puerto Chale.',
     [('DEMO Lancha Safari 1', 10)]),
    ('piratas-adventures', 'avistamiento-ballenas', 'Avistamiento de ballenas', 'paseo', 'por_persona',
     '1100', '65', 1, 10, 'Avistamiento de ballenas en Puerto Chale.',
     [('DEMO Lancha Ballenas 1', 10)]),
    ('piratas-adventures', 'pesca-deportiva', 'Pesca deportiva', 'pesca', 'por_grupo', '5000', '290', 2, 4,
     'Pesca deportiva en Puerto Chale.',
     [('DEMO Panga Chale 1', 4), ('DEMO Panga Chale 2', 4)]),
]


class Command(BaseCommand):
    help = 'Siembra el catálogo real (empresas, servicios, recursos) para pruebas locales.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar-demo', action='store_true',
            help='Borra el demo de seed_local_demo (incluidas TODAS las reservas) y renombra Tours Cabo.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Solo para local (DEBUG=True).')

        # Los alcances de tenancy no se anidan: cada bloque entra y sale del suyo.
        with transaction.atomic():
            if options['limpiar_demo']:
                with scope.como_operador_plataforma():
                    self._limpiar_demo()
            with scope.como_operador_plataforma():
                self._empresas()
            self._servicios()
            self._hotel_y_traslado_la_ventana()
            self._paquetes_la_ventana()

        self.stdout.write(self.style.SUCCESS('Catálogo real sembrado.'))
        self.stdout.write(
            'Placeholders: precios y flota de La Ventana Travel y Piratas Adventures; '
            'llaves de Stripe de Piratas Adventures (sk_test_CAMBIAME).'
        )

    # ------------------------------------------------------------------ limpieza
    def _limpiar_demo(self):
        from apps.bookings.models import Orden, Reserva, Vendedora
        from apps.fleet.models import (
            Embarcacion, Paquete, Personalizacion, Recurso, Servicio,
        )

        self.stdout.write('Borrando reservas y órdenes de prueba...')
        n_reservas = Reserva.objects.count()
        Reserva.objects.all().delete()
        Orden.objects.all().delete()
        self.stdout.write(f'  {n_reservas} reservas borradas')

        Paquete.objects.filter(slug__in=['fin-de-semana-la-paz', 'dia-completo-cabo']).delete()
        servicios_demo = Servicio.objects.filter(slug__in=[
            'paseo-islas', 'cabana-frente-al-mar', 'suite-malecon', 'snorkel-arco', 'avistamiento-ballenas',
        ]).exclude(empresa__slug='piratas-adventures')
        servicios_demo.delete()

        hotel = Empresa.objects.filter(slug='hotel-malecon').first()
        if hotel:
            Vendedora.objects.filter(empresa=hotel).delete()
            usuarios = [m.user for m in MembresiaEmpresa.objects.filter(empresa=hotel)]
            MembresiaEmpresa.objects.filter(empresa=hotel).delete()
            for user in usuarios:
                if not user.is_superuser:
                    user.delete()
            Recurso.objects.filter(empresa=hotel).delete()
            Personalizacion.objects.filter(empresa=hotel).delete()
            Embarcacion.objects.filter(empresa=hotel).delete()
            hotel.delete()
            self.stdout.write('  Hotel Malecón borrado')

        # Recursos sueltos del demo en Sal y Sol (cabañas y lancha de paseo).
        Recurso.objects.filter(empresa__slug='sal-y-sol').filter(
            nombre__startswith='Cabaña ',
        ).delete()
        Recurso.objects.filter(empresa__slug='sal-y-sol', nombre='Lancha Islas 1').delete()

        cabo = Empresa.objects.filter(slug='tours-cabo').first()
        if cabo and not Empresa.objects.filter(slug='la-ventana-travel').exists():
            Recurso.objects.filter(empresa=cabo).delete()
            cabo.slug = 'la-ventana-travel'
            cabo.nombre = 'La Ventana Travel'
            cabo.save(update_fields=['slug', 'nombre'])
            for user in [m.user for m in MembresiaEmpresa.objects.filter(empresa=cabo)]:
                user.username = user.username.replace('tours-cabo', 'la-ventana-travel')
                user.first_name = user.first_name.replace('Tours Cabo', 'La Ventana Travel')
                user.save(update_fields=['username', 'first_name'])
            for vendedora in Vendedora.objects.filter(empresa=cabo):
                vendedora.codigo = vendedora.codigo.replace('tours-cabo', 'la-ventana-travel')
                vendedora.save(update_fields=['codigo'])
            self.stdout.write('  Tours Cabo -> La Ventana Travel')

    # ------------------------------------------------------------------ empresas
    def _empresas(self):
        for slug, (nombre, slug_sede) in EMPRESAS_REALES.items():
            sede = Sede.objects.get(slug=slug_sede)
            empresa, creada = Empresa.objects.get_or_create(
                slug=slug, defaults=dict(sede=sede, nombre=nombre, activo=True, **LLAVES_PLACEHOLDER),
            )
            cambios = []
            if empresa.nombre != nombre:
                empresa.nombre = nombre
                cambios.append('nombre')
            if empresa.sede_id != sede.id:
                empresa.sede = sede
                cambios.append('sede')
            if cambios:
                empresa.save(update_fields=cambios)
            self.stdout.write(f'  Empresa {slug}: {"creada" if creada else "ok"}')

    # ------------------------------------------------------------------ servicios
    def _servicios(self):
        from apps.fleet.models import Embarcacion, Recurso, Servicio

        for (slug_empresa, slug, nombre, tipo, est_precio, precio, precio_usd,
             incluidas, capacidad, descripcion, recursos) in SERVICIOS:
            empresa = Empresa.objects.get(slug=slug_empresa)
            with scope.con_empresa(empresa):
                servicio, creado = Servicio.objects.get_or_create(
                    empresa=empresa, slug=slug,
                    defaults=dict(
                        nombre=nombre, tipo_servicio=tipo,
                        estrategia_cupo='por_recurso_dia', estrategia_precio=est_precio,
                        modo_ocupacion='exclusivo',
                        precio_base=Decimal(precio), precio_base_usd=Decimal(precio_usd),
                        personas_incluidas=incluidas, capacidad_maxima=capacidad,
                        porcentaje_anticipo=30, activo=True, descripcion=descripcion,
                    ),
                )
                for nombre_recurso, cap in recursos:
                    Recurso.objects.get_or_create(
                        empresa=empresa, nombre=nombre_recurso,
                        defaults=dict(servicio=servicio, capacidad_maxima=cap),
                    )
                    # El motor de cupo de las actividades cuenta `Embarcacion`, no `Recurso`:
                    # sin una embarcación a flote, `capacidades_disponibles` es [] y toda
                    # salida responde "sin panga". Se siembran las dos, con el mismo nombre.
                    Embarcacion.objects.get_or_create(
                        empresa=empresa, nombre=nombre_recurso,
                        defaults=dict(clase='grande' if cap >= 5 else 'chica', capacidad_maxima=cap),
                    )
                self.stdout.write(f'  Servicio {slug_empresa}/{slug}: {"creado" if creado else "ok"}')

    # ------------------------------------------------------------------ hotel y traslado de La Ventana Travel
    def _hotel_y_traslado_la_ventana(self):
        """Componentes de los paquetes de La Ventana Travel (una sola empresa):
        hospedaje con habitaciones y traslado de aeropuerto. TODO es placeholder:
        el número de habitaciones, su capacidad y las tarifas no se han confirmado
        con el cliente (ver docs/preguntas-cliente-la-ventana-travel.md)."""
        from apps.fleet.enums import TipoServicio, TipoTraslado
        from apps.fleet.models import Recurso, Servicio, TransporteTarifa

        empresa = Empresa.objects.get(slug='la-ventana-travel')
        with scope.con_empresa(empresa):
            hotel, creado = Servicio.objects.get_or_create(
                empresa=empresa, slug='hospedaje-la-ventana',
                defaults=dict(
                    nombre='Hospedaje en La Ventana', tipo_servicio=TipoServicio.HOSPEDAJE,
                    estrategia_cupo='por_noche', estrategia_precio='por_noche',
                    modo_ocupacion='exclusivo',
                    precio_base=Decimal('2500'), precio_base_usd=Decimal('145'),
                    personas_incluidas=2, porcentaje_anticipo=30, activo=True,
                    descripcion='Habitación con hospedaje en La Ventana. Precio por noche.',
                ),
            )
            self.stdout.write(f'  Servicio la-ventana-travel/hospedaje-la-ventana: {"creado" if creado else "ok"}')
            for nombre, capacidad in (
                ('DEMO Habitación 1', 2), ('DEMO Habitación 2', 2),
                ('DEMO Habitación 3', 2), ('DEMO Habitación 4', 4),
            ):
                Recurso.objects.get_or_create(
                    empresa=empresa, nombre=nombre,
                    defaults=dict(servicio=hotel, capacidad_maxima=capacidad),
                )

            traslado, creado = Servicio.objects.get_or_create(
                empresa=empresa, slug='traslado-aeropuerto-la-ventana',
                defaults=dict(
                    nombre='Traslado al aeropuerto', tipo_servicio=TipoServicio.TRANSPORTE,
                    estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
                    modo_ocupacion='exclusivo', capacidad_maxima=14,
                    permite_anticipo=False, activo=True,
                    descripcion='Traslado redondo aeropuerto-hotel-aeropuerto.',
                ),
            )
            self.stdout.write(f'  Servicio la-ventana-travel/traslado-aeropuerto-la-ventana: {"creado" if creado else "ok"}')
            for p_min, p_max, precio, precio_usd in (
                (1, 4, Decimal('3500'), Decimal('205')),
                (5, None, Decimal('6500'), Decimal('380')),
            ):
                TransporteTarifa.objects.get_or_create(
                    empresa=empresa, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='',
                    personas_min=p_min,
                    defaults=dict(personas_max=p_max, precio=precio, precio_usd=precio_usd, activo=True),
                )

    # ------------------------------------------------------------------ paquetes de La Ventana Travel
    def _paquetes_la_ventana(self):
        """Paquetes A (5 noches) y B (7 noches): llegada el día 1 sin mar, avistamiento
        todos los días de mar seguidos, precio POR PERSONA. USD = MXN / 18 redondeado
        hacia abajo a centavos (tipo de cambio fijo demo; el real se actualizará).
        Capacidad demo: 10 personas = suma de las habitaciones DEMO."""
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio

        empresa = Empresa.objects.get(slug='la-ventana-travel')
        sede = empresa.sede
        definiciones = (
            ('paquete-5-noches', 'Paquete 5 noches', 5, Decimal('45000')),
            ('paquete-7-noches', 'Paquete 7 noches', 7, Decimal('52500')),
        )
        with scope.con_empresa(empresa):
            hotel = Servicio.objects.get(empresa=empresa, slug='hospedaje-la-ventana')
            traslado = Servicio.objects.get(empresa=empresa, slug='traslado-aeropuerto-la-ventana')
            avistamiento = Servicio.objects.get(empresa=empresa, slug='avistamiento-ballenas-orcas')
            for slug, nombre, noches, precio in definiciones:
                usd = (precio / Decimal(18)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                paquete, creado = Paquete.objects.get_or_create(
                    sede=sede, slug=slug,
                    defaults=dict(
                        empresa_lider=empresa, nombre=nombre, precio_ancla=precio,
                        precio_ancla_usd=usd, precio_por_persona=True, activo=True,
                        descripcion=f'{noches} noches de hospedaje, traslado redondo de aeropuerto y '
                                    f'avistamiento de ballenas y orcas del día 2 al {noches}.',
                    ),
                )
                for orden, servicio, extra in (
                    (1, traslado, dict(dia_estancia=1)),
                    (2, hotel, dict(dia_estancia=1, noches=noches)),
                    (3, avistamiento, dict(dia_estancia=2, salidas=noches - 1)),
                ):
                    PaqueteServicio.objects.get_or_create(
                        paquete=paquete, servicio=servicio,
                        defaults=dict(orden=orden, personas_incluidas=10, **extra),
                    )
                paquete.full_clean()
                paquete.validar_configuracion()
                self.stdout.write(f'  Paquete la-ventana/{slug}: {"creado" if creado else "ok"} ({precio} MXN / {usd} USD por persona)')
