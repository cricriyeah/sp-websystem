"""Siembra datos de demo para probar la expansión multi-sede en LOCAL.

NO usar en producción. Idempotente (get_or_create). Crea:
  - Flota de pesca de Sal y Sol (10 pangas)
  - Tarifa legacy de Sal y Sol (para el /reservar clásico)
  - Servicio suelto de paseo (Sal y Sol)
  - Servicio de hospedaje + 3 habitaciones (Sal y Sol) con personalizaciones
  - Un Paquete de Sal y Sol (pesca + hospedaje + brunch)
  - Una segunda Empresa en La Paz ("Hotel Malecón") con su propio hospedaje,
    para probar aislamiento RLS y el marketplace multi-empresa
  - Llaves de Stripe PLACEHOLDER (cámbialas por llaves de test reales en /admin/)

Uso:  venv/Scripts/python.exe manage.py seed_local_demo
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class Command(BaseCommand):
    help = 'Siembra datos de demo multi-sede para pruebas locales.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Solo para local (DEBUG=True).')

        from apps.fleet.models import (
            Embarcacion, Paquete, PaqueteServicio, Personalizacion,
            Recurso, Servicio, ServicioPersonalizacion, Tarifa,
        )

        sede = Sede.objects.get(slug='la-paz')
        sal = Empresa.objects.get(slug='sal-y-sol')

        # --- Sal y Sol: llaves de Stripe placeholder ---
        if not sal.stripe_secret_key:
            sal.stripe_secret_key = 'sk_test_CAMBIAME'
            sal.stripe_publishable_key = 'pk_test_CAMBIAME'
            sal.stripe_webhook_secret = 'whsec_CAMBIAME'
            sal.save(update_fields=['stripe_secret_key', 'stripe_publishable_key', 'stripe_webhook_secret'])
            self.stdout.write(self.style.WARNING(
                'Sal y Sol: llaves Stripe PLACEHOLDER puestas — cámbialas en /admin/tenancy/empresa/'
            ))

        with scope.con_empresa(sal):
            # --- Flota de pesca (10 pangas: 8 de 3, 2 de 5) ---
            for i in range(1, 9):
                Embarcacion.objects.get_or_create(
                    empresa=sal, nombre=f'Panga Chica {i}',
                    defaults={'clase': 'chica', 'capacidad_maxima': 3},
                )
            for i in range(1, 3):
                Embarcacion.objects.get_or_create(
                    empresa=sal, nombre=f'Panga Grande {i}',
                    defaults={'clase': 'grande', 'capacidad_maxima': 5},
                )

            # --- Tarifa legacy (para /reservar sin params) ---
            if Tarifa.de(sal) is None:
                Tarifa.objects.create(
                    empresa=sal, precio=Decimal('4500'), precio_usd=Decimal('260'),
                    precio_persona_extra=Decimal('500'), precio_persona_extra_usd=Decimal('30'),
                )

            # --- Servicio de pesca (ya lo siembra fleet/0018, lo tomamos) ---
            pesca = Servicio.objects.filter(empresa=sal, slug='pesca-deportiva').first()
            if pesca is None:
                pesca = Servicio.objects.create(
                    empresa=sal, nombre='Pesca Deportiva', slug='pesca-deportiva',
                    tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
                    estrategia_precio='por_grupo', modo_ocupacion='exclusivo',
                    precio_base=Decimal('4500'), precio_base_usd=Decimal('260'),
                    personas_incluidas=3, porcentaje_anticipo=30, activo=True,
                )
            # Recursos de pesca = las pangas (para el cupo por servicio)
            for e in Embarcacion.objects.filter(empresa=sal):
                Recurso.objects.get_or_create(
                    empresa=sal, nombre=e.nombre,
                    defaults={'servicio': pesca, 'capacidad_maxima': e.capacidad_maxima},
                )

            # --- Servicio suelto: paseo ---
            paseo, _ = Servicio.objects.get_or_create(
                empresa=sal, slug='paseo-islas',
                defaults=dict(
                    nombre='Paseo a las Islas', tipo_servicio='paseo',
                    estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo',
                    modo_ocupacion='exclusivo', precio_base=Decimal('3000'),
                    precio_base_usd=Decimal('175'), personas_incluidas=6,
                    porcentaje_anticipo=30, activo=True,
                    descripcion='Recorrido a Espíritu Santo con snorkel.',
                ),
            )
            Recurso.objects.get_or_create(
                empresa=sal, nombre='Lancha Islas 1',
                defaults={'servicio': paseo, 'capacidad_maxima': 8},
            )

            # --- Servicio de hospedaje + habitaciones ---
            hosp, _ = Servicio.objects.get_or_create(
                empresa=sal, slug='cabana-frente-al-mar',
                defaults=dict(
                    nombre='Cabaña Frente al Mar', tipo_servicio='hospedaje',
                    estrategia_cupo='por_noche', estrategia_precio='por_noche',
                    modo_ocupacion='exclusivo', precio_base=Decimal('2800'),
                    precio_base_usd=Decimal('160'), personas_incluidas=4,
                    porcentaje_anticipo=50, activo=True,
                    descripcion='Cabaña privada con vista al mar. Precio por noche.',
                ),
            )
            for n in (101, 102, 103):
                Recurso.objects.get_or_create(
                    empresa=sal, nombre=f'Cabaña {n}',
                    defaults={'servicio': hosp, 'capacidad_maxima': 4},
                )

            # --- Personalizaciones ---
            lic, _ = Personalizacion.objects.get_or_create(
                empresa=sal, nombre='Licencia de pesca',
                defaults={'tipo': 'licencia', 'cobrar_por_persona': True, 'cantidad_editable': True},
            )
            brunch, _ = Personalizacion.objects.get_or_create(
                empresa=sal, nombre='Brunch a bordo',
                defaults={'tipo': 'brunch', 'cobrar_por_persona': True},
            )
            ServicioPersonalizacion.objects.get_or_create(
                servicio=pesca, personalizacion=lic,
                defaults={'precio': Decimal('450'), 'precio_usd': Decimal('26'),
                          'obligatorio': False, 'preseleccionado': True},
            )
            ServicioPersonalizacion.objects.get_or_create(
                servicio=pesca, personalizacion=brunch,
                defaults={'precio': Decimal('300'), 'precio_usd': Decimal('18'),
                          'obligatorio': False, 'preseleccionado': False},
            )

            # --- Paquete (una sola empresa: Sal y Sol) ---
            paq, _ = Paquete.objects.get_or_create(
                sede=sede, slug='fin-de-semana-la-paz',
                defaults=dict(
                    empresa_lider=sal, nombre='Fin de Semana en La Paz',
                    descripcion='Pesca + 2 noches de hospedaje frente al mar.',
                    precio_ancla=Decimal('9500'), precio_ancla_usd=Decimal('550'),
                    porcentaje_anticipo=50, activo=True,
                ),
            )
            PaqueteServicio.objects.get_or_create(
                paquete=paq, servicio=pesca,
                defaults={'orden': 1},
            )
            PaqueteServicio.objects.get_or_create(
                paquete=paq, servicio=hosp,
                defaults={'orden': 2},
            )

        # --- Segunda Empresa en La Paz: Hotel Malecón (para aislamiento / marketplace) ---
        hotel, creado = Empresa.objects.get_or_create(
            slug='hotel-malecon',
            defaults=dict(sede=sede, nombre='Hotel Malecón', activo=True,
                          stripe_secret_key='sk_test_HOTEL_CAMBIAME',
                          stripe_publishable_key='pk_test_HOTEL_CAMBIAME',
                          stripe_webhook_secret='whsec_HOTEL_CAMBIAME'),
        )
        with scope.con_empresa(hotel):
            hs, _ = Servicio.objects.get_or_create(
                empresa=hotel, slug='suite-malecon',
                defaults=dict(
                    nombre='Suite Malecón', tipo_servicio='hospedaje',
                    estrategia_cupo='por_noche', estrategia_precio='por_noche',
                    modo_ocupacion='exclusivo', precio_base=Decimal('3200'),
                    precio_base_usd=Decimal('185'), personas_incluidas=2,
                    porcentaje_anticipo=100, activo=True,
                    descripcion='Suite en el malecón de La Paz. Pago completo por adelantado.',
                ),
            )
            for n in (201, 202):
                Recurso.objects.get_or_create(
                    empresa=hotel, nombre=f'Suite {n}',
                    defaults={'servicio': hs, 'capacidad_maxima': 2},
                )

        # --- Segunda SEDE: Los Cabos, con su propia empresa ---
        cabos, _ = Sede.objects.get_or_create(
            slug='los-cabos',
            defaults={'nombre': 'Los Cabos', 'zona_horaria': 'America/Mazatlan', 'activo': True},
        )
        tours, _ = Empresa.objects.get_or_create(
            slug='tours-cabo',
            defaults=dict(sede=cabos, nombre='Tours Cabo', activo=True,
                          stripe_secret_key='sk_test_CABO_CAMBIAME',
                          stripe_publishable_key='pk_test_CABO_CAMBIAME',
                          stripe_webhook_secret='whsec_CABO_CAMBIAME'),
        )
        with scope.con_empresa(tours):
            snorkel, _ = Servicio.objects.get_or_create(
                empresa=tours, slug='snorkel-arco',
                defaults=dict(
                    nombre='Snorkel en el Arco', tipo_servicio='paseo',
                    estrategia_cupo='por_recurso_dia', estrategia_precio='por_persona',
                    modo_ocupacion='exclusivo', precio_base=Decimal('900'),
                    precio_base_usd=Decimal('55'), personas_incluidas=1,
                    porcentaje_anticipo=30, activo=True,
                    descripcion='Tour de snorkel al Arco de Cabo San Lucas.',
                ),
            )
            Recurso.objects.get_or_create(
                empresa=tours, nombre='Panga Arco 1',
                defaults={'servicio': snorkel, 'capacidad_maxima': 10},
            )
            ballenas, _ = Servicio.objects.get_or_create(
                empresa=tours, slug='avistamiento-ballenas',
                defaults=dict(
                    nombre='Avistamiento de Ballenas', tipo_servicio='paseo',
                    estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo',
                    modo_ocupacion='exclusivo', precio_base=Decimal('4200'),
                    precio_base_usd=Decimal('240'), personas_incluidas=4,
                    porcentaje_anticipo=30, activo=True,
                    descripcion='Salida a avistar ballena gris (temporada dic-abr).',
                ),
            )
            Recurso.objects.get_or_create(
                empresa=tours, nombre='Yate Ballenas 1',
                defaults={'servicio': ballenas, 'capacidad_maxima': 12},
            )
            paq_cabo, _ = Paquete.objects.get_or_create(
                sede=cabos, slug='dia-completo-cabo',
                defaults=dict(
                    empresa_lider=tours, nombre='Día Completo en Cabo',
                    descripcion='Snorkel en el Arco + avistamiento de ballenas.',
                    precio_ancla=Decimal('6500'), precio_ancla_usd=Decimal('375'),
                    porcentaje_anticipo=30, activo=True,
                ),
            )
            PaqueteServicio.objects.get_or_create(
                paquete=paq_cabo, servicio=ballenas,
                defaults={'orden': 1},
            )
            PaqueteServicio.objects.get_or_create(
                paquete=paq_cabo, servicio=snorkel,
                defaults={'orden': 2},
            )

        self.stdout.write(self.style.SUCCESS(
            'Demo sembrada.\n'
            '  Sede la-paz    -> sal-y-sol (pesca/paseo/hospedaje + paquete), hotel-malecon (suite)\n'
            '  Sede los-cabos -> tours-cabo (snorkel/ballenas + paquete)\n'
            'Sigue: pon llaves de Stripe TEST reales en /admin/tenancy/empresa/ para las 3 empresas.'
        ))
