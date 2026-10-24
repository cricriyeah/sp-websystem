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
