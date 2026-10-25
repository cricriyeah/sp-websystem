"""Check de arranque para las llaves de Stripe, una fila de Empresa a la vez.

Con una Empresa por marca (ver apps.tenancy), cada una trae sus propias llaves
en `Empresa.stripe_secret_key`/`stripe_webhook_secret`. Este check es la red de
seguridad de ARRANQUE: detecta una llave cruzada que ya haya quedado guardada
(migracion de datos, fixture, el backfill de `tenancy.0002`) sin hablar con la
red. La validacion que de verdad importa corre en `Empresa.clean()`
(apps/tenancy/models.py) — un jefe que teclea una llave cruzada en el admin la
ve rechazada ahi mismo, en caliente; este check no cubre eso, solo lo que ya
esta en la base al arrancar.

Envuelto en try/except DatabaseError: en el deploy que instala esta pieza, el
check corre durante `collectstatic`/`migrate` antes de que la tabla
`tenancy_empresa` exista.
"""
from django.core.checks import Error, Warning, register
from django.db.utils import DatabaseError

# (atributo de Empresa, prefijo que le pone Stripe, codigo, como se llama en el dashboard).
LLAVES_DE_STRIPE = (
    (
        'stripe_secret_key',
        'sk_',
        'payments.E001',
        'la llave secreta (Developers -> API keys)',
    ),
    (
        'stripe_webhook_secret',
        'whsec_',
        'payments.E002',
        'el signing secret del endpoint (Developers -> Webhooks)',
    ),
)


@register()
def revisar_llaves_de_stripe(app_configs, **kwargs):
    """Reporta, por Empresa, las llaves de Stripe que no tienen el prefijo de
    su tipo. El mensaje **nunca incluye el valor** de la llave, solo el slug
    de la Empresa y el nombre del campo.
    """
    from apps.tenancy.models import Empresa

    try:
        empresas = list(Empresa.objects.all())
    except DatabaseError:
        return []

    errores = []
    for empresa in empresas:
        for atributo, prefijo, codigo, de_donde_sale in LLAVES_DE_STRIPE:
            valor = getattr(empresa, atributo, '')
            if valor and not valor.startswith(prefijo):
                errores.append(Error(
                    f'Empresa "{empresa.slug}": {atributo} no empieza con "{prefijo}", '
                    f'asi que no es la llave que este campo espera.',
                    hint=(
                        f'Parece una llave de Stripe capturada en el campo equivocado. '
                        f'En {atributo} va {de_donde_sale}. Corrigela en el admin '
                        f'(Empresas -> {empresa.slug}). Ver docs/deploy/GO-LIVE.md, Fase 5.'
                    ),
                    id=codigo,
                ))

    return errores


# Valor con el que el seed crea una Empresa nueva (`seed_catalogo_real`): pasa el prefijo
# `sk_`/`whsec_`, pero no es una llave de verdad.
MARCA_DE_RELLENO = 'CAMBIAME'


@register()
def revisar_llaves_de_relleno(app_configs, **kwargs):
    """Avisa (sin tumbar el arranque) de las Empresas activas que siguen con llaves de
    relleno y de mezclar llaves de prueba y de produccion entre empresas.

    Es un `Warning` y no un `Error` a proposito: una Empresa apagada o aun sin Stripe es
    un estado normal de un lanzamiento por etapas, y un `Error` impediria el despliegue.
    Una Empresa con la llave de relleno responde 503 al cobrar y su webhook se rechaza:
    el cliente no puede pagar. Como el chequeo anterior, **nunca imprime el valor**.
    """
    from apps.tenancy.models import Empresa

    try:
        empresas = list(Empresa.objects.filter(activo=True))
    except DatabaseError:
        return []

    avisos = []
    modos = {}
    for empresa in empresas:
        for atributo, _prefijo, _codigo, de_donde_sale in LLAVES_DE_STRIPE:
            valor = getattr(empresa, atributo, '') or ''
            if MARCA_DE_RELLENO in valor.upper():
                avisos.append(Warning(
                    f'Empresa "{empresa.slug}": {atributo} sigue con el valor de relleno del seed.',
                    hint=(
                        f'Pon {de_donde_sale} real en el admin (Empresas -> {empresa.slug}) '
                        f'antes de venderle a un cliente. Ver docs/deploy/GO-LIVE.md.'
                    ),
                    id='payments.W001',
                ))
        secreta = empresa.stripe_secret_key or ''
        if secreta.startswith('sk_') and MARCA_DE_RELLENO not in secreta.upper():
            modos[empresa.slug] = 'prueba' if secreta.startswith(('sk_test_', 'rk_test_')) else 'produccion'

    if len(set(modos.values())) > 1:
        en_prueba = sorted(slug for slug, modo in modos.items() if modo == 'prueba')
        en_produccion = sorted(slug for slug, modo in modos.items() if modo == 'produccion')
        avisos.append(Warning(
            'Hay Empresas activas con llaves de prueba y otras con llaves de produccion '
            f'(prueba: {", ".join(en_prueba)}; produccion: {", ".join(en_produccion)}).',
            hint='Un cobro de prueba en una empresa y real en otra suele ser un olvido al lanzar.',
            id='payments.W002',
        ))

    return avisos


@register()
def revisar_cifrado_de_llaves(app_configs, **kwargs):
    """Vigila que las llaves de Stripe no queden en texto plano en la base.

    - E003: una `sk_live_` en texto plano. Nunca debe haber una llave de produccion legible en la base
      (decision ADR-002): o se pone `STRIPE_KEYS_ENCRYPTION_KEY` y se corre `cifrar_llaves_stripe`, o no
      se despliega.
    - E004: la variable existe pero no es una clave Fernet valida; sin esto el primer cobro fallaria.
    - W003: hay clave pero quedan valores en texto plano (falta correr `cifrar_llaves_stripe`).
    Lee la base en crudo porque el campo ya devuelve el texto real. Nunca incluye el valor.
    """
    from django.db import connection

    from apps.tenancy.campos import PREFIJO, claves_de_cifrado, clave_valida
    from apps.tenancy.models import Empresa

    problemas = []
    claves = claves_de_cifrado()
    if claves and not all(clave_valida(clave) for clave in claves):
        problemas.append(Error(
            'STRIPE_KEYS_ENCRYPTION_KEY no es una clave Fernet valida.',
            hint='Genera una: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
            id='payments.E004',
        ))
        return problemas

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT slug, stripe_secret_key, stripe_webhook_secret FROM {Empresa._meta.db_table}'
            )
            filas = cursor.fetchall()
    except DatabaseError:
        return problemas

    for slug, secreta, webhook in filas:
        if secreta and not secreta.startswith(PREFIJO) and secreta.startswith('sk_live_'):
            problemas.append(Error(
                f'Empresa "{slug}": la llave secreta de produccion esta en texto plano en la base.',
                hint='Define STRIPE_KEYS_ENCRYPTION_KEY y corre: python manage.py cifrar_llaves_stripe. '
                     'Ver docs/deploy/GO-LIVE.md.',
                id='payments.E003',
            ))
        elif claves and any(valor and not valor.startswith(PREFIJO) for valor in (secreta, webhook)):
            problemas.append(Warning(
                f'Empresa "{slug}": hay llaves de Stripe en texto plano aunque el cifrado esta encendido.',
                hint='Corre: python manage.py cifrar_llaves_stripe',
                id='payments.W003',
            ))
    return problemas
