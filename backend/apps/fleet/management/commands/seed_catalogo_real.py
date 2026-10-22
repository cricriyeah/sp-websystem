"""Siembra el catálogo operativo real en LOCAL: empresas, servicios y recursos.

NO usar en producción (pone llaves de Stripe placeholder). Idempotente.

Estructura de negocio:
  La Paz       -> Sal y Sol Sportfishing (pesca deportiva)
                  DLS Transporte (traslados; el slug se queda `transporte-la-paz`
                  porque el webhook de Stripe y el frontend dependen de él)
                  Paquete cruza-empresa Pesca + Traslado (lo siembra seed_local_demo)
  La Ventana   -> La Ventana Travel (pesca con mosca, avistamiento de ballenas y orcas)
  Puerto Chale -> Piratas Adventures (safari marino, avistamiento de ballenas, pesca)

De La Ventana Travel y Piratas Adventures ya hay datos confirmados por ellos (ver `DATOS_REALES`):
estudios, pesca con mosca, safari marino y su flota. Lo que sigue siendo
PLACEHOLDER (avistamiento de ballenas, precio de la pesca de Piratas, hospedaje por noche, los
paquetes y las lanchas "DEMO ...") se reemplaza desde el admin. Los paquetes de La Ventana
(precio por persona, mar en varios días) sí se siembran.

`--limpiar-demo` borra lo que dejó seed_local_demo y no es real (Hotel Malecón, paseo,
cabañas, snorkel, paquetes demo, TODAS las reservas y órdenes de prueba) y convierte la
empresa demo Tours Cabo en La Ventana Travel. Hazlo una sola vez, antes de sembrar.

Uso:  venv/Scripts/python.exe manage.py seed_catalogo_real [--limpiar-demo]

`--produccion` lo hace apto para la base real: no exige DEBUG, crea solo las empresas que falten (nombre y sede, sin
llaves de Stripe ni jefe; las que ya existen no se tocan), no siembra lanchas ni habitaciones «DEMO» y no borra nada. Solo crea o
actualiza servicios, textos, precios, horarios, estudios y paquetes, y al final imprime lo que sigue siendo relleno
sin confirmar. La flota real (pangas de Sal y Sol, vehículos de DLS) se captura en el admin.
"""
from datetime import time
from decimal import Decimal

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

# (empresa, slug, nombre, tipo, estrategia_precio, precio, personas_incluidas,
#  capacidad_maxima, descripcion, [(recurso, capacidad)])
SERVICIOS = [
    ('la-ventana-travel', 'pesca-con-mosca', 'Pesca con mosca', 'pesca', 'por_grupo',
     '6000', 2, 3, 'Pesca con mosca (fly fishing) en La Ventana.',
     [('DEMO Panga La Ventana 1', 3), ('DEMO Panga La Ventana 2', 3)]),
    ('la-ventana-travel', 'avistamiento-ballenas-orcas', 'Avistamiento de ballenas y orcas', 'paseo',
     'por_persona', '1200', 1, 12,
     'Salida al mar para ver ballenas y orcas según la temporada; la logística es la misma.',
     [('DEMO Lancha La Ventana 1', 12), ('DEMO Lancha La Ventana 2', 12)]),
    ('piratas-adventures', 'safari-marino', 'Safari marino', 'paseo', 'por_persona', '900', 1, 10,
     'Safari marino en Puerto Chale.',
     [('DEMO Lancha Safari 1', 10)]),
    ('piratas-adventures', 'avistamiento-ballenas', 'Avistamiento de ballenas', 'paseo', 'por_persona',
     '1100', 1, 10, 'Avistamiento de ballenas en Puerto Chale.',
     [('DEMO Lancha Ballenas 1', 10)]),
    ('piratas-adventures', 'pesca-deportiva', 'Pesca deportiva', 'pesca', 'por_grupo', '5000', 2, 4,
     'Pesca deportiva en Puerto Chale.',
     [('DEMO Panga Chale 1', 4), ('DEMO Panga Chale 2', 4)]),
]


# Lo que La Ventana Travel y Piratas Adventures confirmaron por WhatsApp (2026-09-21 y 2026-10-09).
# Se aplica por UPDATE sobre lo ya sembrado. `incluye`: hasta 8 renglones de 80 caracteres.
# No hay precio de la licencia de pesca: es un extra de cada empresa, sin importe confirmado todavía.
INCLUYE_AVISTAMIENTO = {
    'es': ['Salida diaria, de 7:00 a 8:00 am, de La Ventana o Bahía de los Sueños',
           'El tour dura de 5 a 6 horas aproximadamente',
           'Algo de comer, aguas y refrescos',
           'Equipo para snorkelear',
           'Snorkel en un arrecife',
           'Buscamos animales para intentar nadar con ellos'],
    'en': ['Daily departure, 7:00 to 8:00 am, from La Ventana or Bahía de los Sueños',
           'The tour lasts about 5 to 6 hours',
           'Some food, water and soft drinks',
           'Snorkeling gear',
           'Snorkeling at a reef',
           'We look for animals to try to swim with them'],
}

# Lo que confirmó el dueño el 2026-10-21 (precios SIN IVA). Sal y Sol: 8 pangas de 8, salida de 5 a 7, 10,800 por viaje
# (600 USD a 18) para 1 o 2 personas y 1,350 (75 USD) por cada persona extra desde la tercera. El dueño dio estos
# precios en dólares el 2026-10-22; antes se había anotado 12,000 / 1,800 MXN. La Ventana: 5 pangas de 8, salida de 7 a 8.
INCLUYE_PESCA_SAL_Y_SOL = {
    'es': ['Desayuno ligero y comida a bordo', 'Aperitivos: fruta y frituras', 'Bebidas',
           'Cubre 1 o 2 personas; desde la tercera se suma un cargo por persona'],
    'en': ['Light breakfast and lunch on board', 'Snacks: fruit and chips', 'Drinks',
           'Covers 1 or 2 people; from the third on, a per-person charge applies'],
}
INCLUYE_AMENIDADES_VENTANA = {
    'es': ['Comida ligera, aperitivos y bebidas incluidos', 'Equipo para snorkelear'],
    'en': ['Light meal, snacks and drinks included', 'Snorkeling gear'],
}

DATOS_REALES = {
    ('sal-y-sol', 'pesca-deportiva'): dict(
        nombre='Pesca deportiva',
        estrategia_precio='por_grupo', precio_base=Decimal('10800'), precio_persona_extra=Decimal('1350'),
        # La panga lleva 8, pero un viaje de pesca va con 5 como máximo (dueño, 2026-10-22).
        personas_incluidas=2, capacidad_maxima=5,
        descripcion='Viaje de pesca deportiva en La Paz, de 5:00 a 7:00 am de salida, en panga para hasta 5 personas. '
                    'La licencia de pesca se tramita aparte, para las personas que elijas.',
        incluye=INCLUYE_PESCA_SAL_Y_SOL,
    ),
    ('la-ventana-travel', 'pesca-con-mosca'): dict(
        nombre='Pesca con mosca',
        estrategia_precio='por_grupo', precio_base=Decimal('12000'), precio_persona_extra=Decimal('0'),
        personas_incluidas=3, capacidad_maxima=3,
        descripcion='Un día de pesca con mosca (fly fishing) en La Ventana, para un grupo de hasta 3 personas, '
                    'sin cargo por persona extra. La licencia de pesca no está incluida.',
        incluye={'es': ['Un día de pesca con mosca', 'Salida de 7:00 a 8:00 am', 'Para 3 personas como máximo',
                        *INCLUYE_AMENIDADES_VENTANA['es']],
                 'en': ['A full day of fly fishing', 'Departure from 7:00 to 8:00 am', 'For 3 people at most',
                        *INCLUYE_AMENIDADES_VENTANA['en']]},
    ),
    ('la-ventana-travel', 'avistamiento-ballenas-orcas'): dict(
        nombre='Avistamiento de ballenas y orcas',
        estrategia_precio='por_persona', modo_ocupacion='compartido',
        precio_base=Decimal('5000'), precio_persona_extra=Decimal('0'),
        personas_incluidas=1, capacidad_maxima=8,
        descripcion='Salida diaria al mar para buscar ballenas y orcas e intentar nadar con ellas, con snorkel en un '
                    'arrecife. Precio por persona en lancha compartida; '
                    'para un grupo privado (hasta 10 personas) el costo es de $20,000 MXN: consúltalo por WhatsApp.',
        incluye=INCLUYE_AVISTAMIENTO,
    ),
    ('la-ventana-travel', 'hospedaje-la-ventana'): dict(
        nombre='Hotel Casa Arrecife',
        solo_en_paquete=True,  # no se vende como servicio aparte: solo dentro de los paquetes
        descripcion='Seis estudios (suites) para 2 personas, cada uno con una cama king size. Precio por noche. '
                    'A 1 km de la playa de La Ventana, con restaurantes a menos de 1 km, a 2.2 km del centro de '
                    'La Ventana y a 37 km del aeropuerto de La Paz. Distancias en línea recta: el recorrido real puede variar.',
        incluye={'es': ['Estudio para 2 personas con una cama king size',
                        'Entrada de 14:00 a 15:00 y salida de 11:00 a 12:00',
                        'Niños de cualquier edad son bienvenidos',
                        'No se pueden agregar camas extra ni cunas'],
                 'en': ['Studio for 2 people with one king size bed',
                        'Check-in 2:00 to 3:00 pm, check-out 11:00 am to 12:00 pm',
                        'Children of all ages are welcome',
                        'Extra beds and cribs cannot be added']},
    ),
    ('piratas-adventures', 'safari-marino'): dict(
        nombre='Safari marino',
        estrategia_precio='por_grupo', precio_base=Decimal('14000'), precio_persona_extra=Decimal('2000'),
        personas_incluidas=6, capacidad_maxima=8,
        descripcion='Safari marino en Puerto Chale para un grupo de 6 personas, con hasta 2 personas más '
                    'por un cargo adicional. Si el grupo es más grande se puede sumar otra embarcación '
                    'avisando con un poco de anticipación.',
        incluye={'es': ['Refrescos, aguas naturales, agua mineral y sueros sin costo',
                        'A veces también cervezas, si lo deseas',
                        'Comida opcional, sin costo: sándwiches, burritos...',
                        'Puedes traer tus propias bebidas y alimentos'],
                 'en': ['Sodas, fresh water, mineral water and electrolyte drinks at no cost',
                        'Sometimes also beer, if you wish',
                        'Optional food at no cost: sandwiches, burritos...',
                        'You can bring your own drinks and food']},
    ),
    ('piratas-adventures', 'pesca-deportiva'): dict(
        capacidad_maxima=4,
        descripcion='Pesca deportiva en Puerto Chale, hasta 4 personas. La licencia de pesca no está incluida.',
        incluye={'es': ['Refrescos, aguas naturales, agua mineral y sueros sin costo',
                        'Comida opcional, sin costo: sándwiches, burritos...',
                        'Puedes traer tus propias bebidas y alimentos'],
                 'en': ['Sodas, fresh water, mineral water and electrolyte drinks at no cost',
                        'Optional food at no cost: sandwiches, burritos...',
                        'You can bring your own drinks and food']},
    ),
}


# Flota de La Ventana para sus salidas al mar: no hay un número fijo, se pone 5 (3 de 7 personas y 2 de 10).
PANGAS_VENTANA = tuple((f'Panga La Ventana {n}', 8) for n in range(1, 6))

# Flota de Sal y Sol: 8 pangas de 8. Los nombres son genéricos; se renombran en el admin.
PANGAS_SAL_Y_SOL = tuple((f'Panga {n}', 8) for n in range(1, 9))

# Tarifas de DLS Transporte (sin IVA). La vuelta completa cuesta según la zona del hotel: centro 3,500; Puerta Cortés o
# periferia 3,800. La recepción en aeropuerto es de 2,700. Para el redondo de actividad el dueño no dio precio propio:
# se aplica la misma vuelta completa por zona (CONFIRMAR).
TARIFAS_DLS = (
    ('recepcion_aeropuerto', '', Decimal('2700')),
    ('redondo_aeropuerto', 'centro', Decimal('3500')),
    ('redondo_aeropuerto', 'periferia', Decimal('3800')),
    ('redondo_actividad', 'centro', Decimal('3500')),
    ('redondo_actividad', 'periferia', Decimal('3800')),
)


class Command(BaseCommand):
    help = 'Siembra el catálogo real (empresas, servicios, recursos) para pruebas locales.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--produccion', action='store_true',
            help='Para la base real: sin DEBUG, sin empresas ni llaves nuevas, sin lanchas ni habitaciones DEMO.',
        )
        parser.add_argument(
            '--limpiar-demo', action='store_true',
            help='Borra el demo de seed_local_demo (incluidas TODAS las reservas) y renombra Tours Cabo.',
        )

    def handle(self, *args, **options):
        produccion = options['produccion']
        if not settings.DEBUG and not produccion:
            raise CommandError('Solo para local (DEBUG=True). Para la base real usa --produccion.')
        if produccion and options['limpiar_demo']:
            raise CommandError('--limpiar-demo borra reservas: no se combina con --produccion.')

        # Los alcances de tenancy no se anidan: cada bloque entra y sale del suyo.
        with transaction.atomic():
            if options['limpiar_demo']:
                with scope.como_operador_plataforma():
                    self._limpiar_demo()
            with scope.como_operador_plataforma():
                if produccion:
                    self._empresas_de_produccion()
                else:
                    self._empresas()
            self._servicios(con_demo=not produccion)
            self._hotel_y_traslado_la_ventana(con_demo=not produccion)
            self._la_paz(con_flota=produccion)
            self._desactivar_sedes()
            # Los horarios van antes de los datos reales: `_datos_reales` valida cada servicio completo y uno que
            # pide hora sin rango no pasa (en una base nueva los servicios nacen sin él).
            self._horarios_demo()
            self._datos_reales()
            self._paquetes_la_ventana()

        self.stdout.write(self.style.SUCCESS('Catálogo real sembrado.'))
        if produccion:
            self.stdout.write(
                'Relleno SIN confirmar que quedó en la base (revisar en el admin antes de vender): precio de la noche de '
                'hospedaje (2,500), tarifas del traslado de La Ventana (3,500 / 6,500), precio por persona de los paquetes, '
                'precio de la pesca de Piratas Adventures y los horarios de cada servicio salvo Sal y Sol. '
                'La flota (pangas, vehículos) y las llaves de Stripe de cada empresa se capturan en el admin.'
            )
        else:
            self.stdout.write(
                'Placeholders: precio de la pesca de Piratas Adventures, '
                'precio del hospedaje, paquetes y llaves de Stripe de Piratas Adventures (sk_test_CAMBIAME).'
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
    def _empresas_de_produccion(self):
        """En la base real crea las empresas que falten, solo con nombre y sede: sin llaves de Stripe, sin jefe ni
        vendedora (eso se captura en el admin: Empresas > la empresa, y Alta de usuario). Las que ya existen no se
        tocan: si alguien las dio de alta con otro nombre o sus llaves, se respeta."""
        for slug, (nombre, slug_sede) in EMPRESAS_REALES.items():
            sede = Sede.objects.get(slug=slug_sede)
            _, creada = Empresa.objects.get_or_create(slug=slug, defaults=dict(sede=sede, nombre=nombre, activo=True))
            self.stdout.write(f'  Empresa {slug}: {"creada (sin llaves ni jefe)" if creada else "ok"}')

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
    def _servicios(self, con_demo=True):
        from apps.fleet.models import Embarcacion, Recurso, Servicio

        for (slug_empresa, slug, nombre, tipo, est_precio, precio,
             incluidas, capacidad, descripcion, recursos) in SERVICIOS:
            empresa = Empresa.objects.get(slug=slug_empresa)
            with scope.con_empresa(empresa):
                servicio, creado = Servicio.objects.get_or_create(
                    empresa=empresa, slug=slug,
                    defaults=dict(
                        nombre=nombre, tipo_servicio=tipo,
                        estrategia_cupo='por_recurso_dia', estrategia_precio=est_precio,
                        modo_ocupacion='exclusivo',
                        precio_base=Decimal(precio),
                        personas_incluidas=incluidas, capacidad_maxima=capacidad,
                        porcentaje_anticipo=30, activo=True, descripcion=descripcion,
                    ),
                )
                # Las lanchas «DEMO» son de la base local: en la real la flota se captura en el admin.
                for nombre_recurso, cap in (recursos if con_demo else []):
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
    def _hotel_y_traslado_la_ventana(self, con_demo=True):
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
                    precio_base=Decimal('2500'),
                    personas_incluidas=2, porcentaje_anticipo=30, activo=True,
                    descripcion='Habitación con hospedaje en La Ventana. Precio por noche.',
                ),
            )
            self.stdout.write(f'  Servicio la-ventana-travel/hospedaje-la-ventana: {"creado" if creado else "ok"}')
            for nombre, capacidad in (
                (('DEMO Habitación 1', 2), ('DEMO Habitación 2', 2),
                 ('DEMO Habitación 3', 2), ('DEMO Habitación 4', 4)) if con_demo else ()
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
            if not traslado.solo_en_paquete:
                traslado.solo_en_paquete = True
                traslado.save(update_fields=['solo_en_paquete'])
            self.stdout.write(f'  Servicio la-ventana-travel/traslado-aeropuerto-la-ventana: {"creado" if creado else "ok"}')
            for p_min, p_max, precio in (
                (1, 4, Decimal('3500')),
                (5, None, Decimal('6500')),
            ):
                TransporteTarifa.objects.get_or_create(
                    empresa=empresa, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='',
                    personas_min=p_min,
                    defaults=dict(personas_max=p_max, precio=precio, activo=True),
                )

    # ------------------------------------------------------------------ La Paz: Sal y Sol y DLS Transporte
    def _la_paz(self, con_flota):
        """Sal y Sol (pesca deportiva, su licencia y, en la base real, sus 8 pangas) y DLS Transporte (traslados y
        tarifas). Sin hoteles ni vehículos: los puntos de encuentro y la flota de DLS se capturan en el admin."""
        from apps.fleet.enums import TipoServicio
        from apps.fleet.models import (
            Embarcacion, Paquete, Personalizacion, Recurso, Servicio, ServicioPersonalizacion, TransporteTarifa,
        )

        sal = Empresa.objects.get(slug='sal-y-sol')
        with scope.con_empresa(sal):
            pesca, _ = Servicio.objects.get_or_create(
                empresa=sal, slug='pesca-deportiva',
                defaults=dict(
                    nombre='Pesca deportiva', tipo_servicio=TipoServicio.PESCA,
                    estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo', modo_ocupacion='exclusivo',
                    precio_base=Decimal('10800'), personas_incluidas=2, porcentaje_anticipo=30, activo=True,
                    pide_hora=True, hora_apertura=time(5, 0), hora_cierre=time(7, 0), paso_hora_minutos=15,
                ),
            )
            licencia, _ = Personalizacion.objects.get_or_create(
                empresa=sal, nombre='Licencia de pesca',
                defaults=dict(tipo='licencia', cobrar_por_persona=True, cantidad_editable=True),
            )
            enlace, _ = ServicioPersonalizacion.objects.get_or_create(
                servicio=pesca, personalizacion=licencia, defaults=dict(precio=Decimal('300')),
            )
            enlace.precio = Decimal('300')
            enlace.activo = True
            enlace.save(update_fields=['precio', 'activo'])
            # El lunch ya va incluido en el viaje: el brunch como extra de pago deja de ofrecerse.
            ServicioPersonalizacion.objects.filter(
                servicio=pesca, personalizacion__nombre='Brunch a bordo',
            ).update(activo=False)
            if con_flota:
                for nombre, capacidad in PANGAS_SAL_Y_SOL:
                    Recurso.objects.get_or_create(
                        empresa=sal, nombre=nombre, defaults=dict(servicio=pesca, capacidad_maxima=capacidad),
                    )
                    Embarcacion.objects.get_or_create(
                        empresa=sal, nombre=nombre,
                        defaults=dict(clase='grande', capacidad_maxima=capacidad),
                    )
            self.stdout.write('  Sal y Sol: pesca deportiva, licencia y flota al día')

        dls = Empresa.objects.get(slug='transporte-la-paz')
        with scope.con_empresa(dls):
            Servicio.objects.get_or_create(
                empresa=dls, slug='traslados-la-paz',
                defaults=dict(
                    nombre='Traslados Privados La Paz', tipo_servicio=TipoServicio.TRANSPORTE,
                    estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', modo_ocupacion='exclusivo',
                    capacidad_maxima=14, permite_anticipo=False, activo=False,
                    descripcion='Traslados privados en La Paz: del aeropuerto al hotel y de regreso, y del hotel a la actividad.',
                ),
            )
            vigentes = set()
            for tipo, zona, precio in TARIFAS_DLS:
                tarifa, _ = TransporteTarifa.objects.get_or_create(
                    empresa=dls, tipo_traslado=tipo, zona=zona, personas_min=1,
                    defaults=dict(personas_max=None, precio=precio, activo=True),
                )
                tarifa.personas_max = None
                tarifa.precio = precio
                tarifa.activo = True
                tarifa.save(update_fields=['personas_max', 'precio', 'activo'])
                vigentes.add(tarifa.pk)
            # DLS Transporte queda apagado por ahora, y con él su paquete con Sal y Sol (Pesca + Traslado).
            Servicio.objects.filter(empresa=dls, slug='traslados-la-paz').update(activo=False)
            # Las tarifas de relleno de antes (por rangos de personas, sin zona) ya no valen.
            TransporteTarifa.objects.filter(empresa=dls).exclude(pk__in=vigentes).update(activo=False)
            self.stdout.write('  DLS Transporte: tarifas por zona al día; servicio DESACTIVADO por ahora')
        with scope.como_operador_plataforma():
            Paquete.objects.filter(slug='pesca-traslado').update(activo=False)
            self.stdout.write('  Paquete pesca-traslado (Sal y Sol + DLS) desactivado')

    def _desactivar_sedes(self):
        """Puerto Chale queda apagada por ahora: sin página, sin selector y sin reservas."""
        with scope.como_operador_plataforma():
            n = Sede.objects.filter(slug='puerto-chale').update(activo=False)
        self.stdout.write(f'  Sede puerto-chale desactivada ({n})')

    # ------------------------------------------------------------------ datos confirmados por las empresas
    def _datos_reales(self):
        """Aplica lo que La Ventana Travel y Piratas Adventures ya confirmaron: textos y precios por UPDATE
        (corrige lo ya sembrado), su flota y los seis
        estudios del hospedaje. Los recursos "DEMO Habitación" se quitan solo si nadie los ha ocupado."""
        from django.db.models import ProtectedError

        from apps.fleet.enums import TipoServicio
        from apps.fleet.models import Embarcacion, Recurso, Servicio

        for (slug_empresa, slug), campos in DATOS_REALES.items():
            empresa = Empresa.objects.get(slug=slug_empresa)
            with scope.con_empresa(empresa):
                servicio = Servicio.objects.get(empresa=empresa, slug=slug)
                for campo, valor in campos.items():
                    setattr(servicio, campo, valor)
                servicio.full_clean()
                servicio.save()
                self.stdout.write(f'  Datos reales {slug_empresa}/{slug}: aplicados')

        empresa = Empresa.objects.get(slug='la-ventana-travel')
        with scope.con_empresa(empresa):
            avistamiento = Servicio.objects.get(empresa=empresa, slug='avistamiento-ballenas-orcas')
            # Los dos tours a Isla Cerralvo que sembró una versión anterior de este comando eran una lectura
            # equivocada del mensaje de la empresa: ese tour ES el avistamiento. Se quitan si nadie los ha reservado.
            for slug_viejo in ('tour-isla-cerralvo-privado', 'tour-isla-cerralvo-compartido'):
                viejo = Servicio.objects.filter(empresa=empresa, slug=slug_viejo).first()
                if viejo is None:
                    continue
                Recurso.objects.filter(empresa=empresa, servicio=viejo).update(servicio=avistamiento)
                try:
                    with transaction.atomic():
                        viejo.delete()
                    self.stdout.write(f'  Servicio {slug_viejo}: quitado')
                except ProtectedError:
                    self.stdout.write(f'  Servicio {slug_viejo}: tiene reservas, se queda (desactivar a mano)')
            # El motor de cupo cuenta `Embarcacion` (de la empresa, no del servicio): las pangas sirven al avistamiento.
            for nombre, cap in PANGAS_VENTANA:
                Recurso.objects.get_or_create(
                    empresa=empresa, nombre=nombre, defaults=dict(servicio=avistamiento, capacidad_maxima=cap),
                )
                Embarcacion.objects.get_or_create(
                    empresa=empresa, nombre=nombre,
                    defaults=dict(clase='grande' if cap >= 5 else 'chica', capacidad_maxima=cap),
                )

            hospedaje = Servicio.objects.get(empresa=empresa, slug='hospedaje-la-ventana')
            for numero in range(1, 7):
                Recurso.objects.get_or_create(
                    empresa=empresa, nombre=f'Estudio {numero}',
                    defaults=dict(servicio=hospedaje, capacidad_maxima=2),
                )
            for demo in Recurso.objects.filter(empresa=empresa, nombre__startswith='DEMO Habitación'):
                try:
                    with transaction.atomic():
                        demo.delete()
                except ProtectedError:
                    self.stdout.write(f'  {demo.nombre}: tiene reservas, se queda (desactivar a mano)')

        empresa = Empresa.objects.get(slug='piratas-adventures')
        with scope.con_empresa(empresa):
            # Dos embarcaciones para unas 14 personas; para la actividad, máximo 8 por salida.
            safari = Servicio.objects.get(empresa=empresa, slug='safari-marino')
            for numero in (1, 2):
                nombre = f'Embarcación Piratas {numero}'
                Recurso.objects.get_or_create(
                    empresa=empresa, nombre=nombre, defaults=dict(servicio=safari, capacidad_maxima=8),
                )
                Embarcacion.objects.get_or_create(
                    empresa=empresa, nombre=nombre, defaults=dict(clase='grande', capacidad_maxima=8),
                )

    # ------------------------------------------------------------------ paquetes de La Ventana Travel
    def _paquetes_la_ventana(self):
        """Paquetes A (5 noches) y B (7 noches): llegada el día 1 sin mar, avistamiento
        todos los días de mar seguidos, precio POR PERSONA. USD = MXN / 18 redondeado
        hacia abajo a centavos (tipo de cambio fijo demo; el real se actualizará).
        Capacidad: 12 en el hotel (6 estudios de 2) y 8 en el mar (pangas de 8)."""
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
                paquete, creado = Paquete.objects.get_or_create(
                    sede=sede, slug=slug,
                    defaults=dict(
                        empresa_lider=empresa, nombre=nombre, precio_ancla=precio,
                        estrategia_precio='por_persona', pide_hora=False, activo=True,
                        descripcion=f'{noches} noches de hospedaje, traslado redondo de aeropuerto y '
                                    f'avistamiento de ballenas y orcas del día 2 al {noches}.',
                    ),
                )
                # Lo que incluye el paquete: las mismas amenidades que la pesca con mosca; el hospedaje no lleva comida.
                paquete.incluye = {
                    'es': [f'{noches} noches de hospedaje en el Hotel Casa Arrecife', 'Traslado redondo del aeropuerto al hotel',
                           f'Salidas al mar para ver ballenas y orcas, del día 2 al {noches}',
                           *INCLUYE_AMENIDADES_VENTANA['es'], 'El hospedaje no incluye comida'],
                    'en': [f'{noches} nights at Hotel Casa Arrecife', 'Round-trip airport transfer',
                           f'Sea trips to see whales and orcas, from day 2 to day {noches}',
                           *INCLUYE_AMENIDADES_VENTANA['en'], 'Lodging does not include meals'],
                }
                for orden, servicio, extra in (
                    (1, traslado, dict(dia_estancia=1)),
                    (2, hotel, dict(dia_estancia=1, noches=noches)),
                    (3, avistamiento, dict(dia_estancia=2, salidas=noches - 1)),
                ):
                    componente, _ = PaqueteServicio.objects.get_or_create(
                        paquete=paquete, servicio=servicio,
                        defaults=dict(orden=orden, personas_incluidas=12 if servicio is hotel else 8, **extra),
                    )
                    componente.personas_incluidas = 12 if servicio is hotel else 8
                    componente.save(update_fields=['personas_incluidas'])
                if paquete.pide_hora:
                    paquete.pide_hora = False
                    paquete.save(update_fields=['pide_hora'])
                paquete.full_clean()
                paquete.save()
                paquete.validar_configuracion()
                self.stdout.write(f'  Paquete la-ventana/{slug}: {"creado" if creado else "ok"} ({precio} MXN por persona)')

    # ------------------------------------------------------------------ horarios (DEMO)
    def _horarios_demo(self):
        """Rango de horas y paso de cada servicio, o sin hora. TODO es placeholder: ninguna empresa ha
        confirmado su horario real (ver docs/preguntas-cliente-la-ventana-travel.md). Se aplica por
        UPDATE para que también corrija servicios ya sembrados."""
        from apps.fleet.models import Servicio

        # (empresa, slug) -> (apertura, cierre, paso en minutos) | None = no pide hora
        horarios = {
            ('sal-y-sol', 'pesca-deportiva'): (time(5, 0), time(7, 0), 15),
            ('transporte-la-paz', 'traslados-la-paz'): (time(6, 0), time(22, 0), 30),
            ('la-ventana-travel', 'pesca-con-mosca'): (time(7, 0), time(8, 0), 30),
            ('la-ventana-travel', 'avistamiento-ballenas-orcas'): (time(7, 0), time(8, 0), 30),
            ('la-ventana-travel', 'hospedaje-la-ventana'): None,
            ('la-ventana-travel', 'traslado-aeropuerto-la-ventana'): None,
            ('piratas-adventures', 'safari-marino'): (time(9, 0), time(11, 0), 60),
            ('piratas-adventures', 'avistamiento-ballenas'): (time(8, 0), time(10, 0), 60),
            ('piratas-adventures', 'pesca-deportiva'): (time(5, 0), time(7, 0), 15),
        }
        for (slug_empresa, slug), horario in horarios.items():
            empresa = Empresa.objects.filter(slug=slug_empresa).first()
            if empresa is None:
                continue
            with scope.con_empresa(empresa):
                servicios = Servicio.objects.filter(empresa=empresa, slug=slug)
                if horario is None:
                    servicios.update(pide_hora=False)
                else:
                    apertura, cierre, paso = horario
                    servicios.update(
                        pide_hora=True, hora_apertura=apertura, hora_cierre=cierre, paso_hora_minutos=paso,
                    )
        self.stdout.write('  Horarios demo aplicados a los servicios.')
