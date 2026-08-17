"""Check de arranque para las llaves de Stripe.

Existe por un caso real: en Render quedo el signing secret del webhook
(`whsec_...`) capturado dentro de `STRIPE_SECRET_KEY`. Stripe rechazaba cada
llamada con `AuthenticationError`, `crear-pago` devolvia 502 y el checkout
mostraba un error generico. Nada en el sintoma apuntaba a la causa: el sitio
estaba arriba, la base contestaba, la tarifa se veia y los tests pasaban.

Las tres llaves de Stripe tienen prefijo fijo, asi que un cruce se detecta sin
hablar con la red. Es Error y no Warning a proposito: el `buildCommand` de Render
corre `collectstatic` y `migrate`, los dos pasan por los system checks, asi que
una llave cruzada se vuelve un deploy que no sale en vez de un checkout roto.

**Lo que este check no puede hacer**: decir si la llave es *valida*, solo si
tiene la forma que le toca. Una `sk_test_` de otra cuenta pasa igual. Tampoco
cubre el caso de que las variables no esten disponibles en el build — ahi el
check no ve nada y no reporta nada. Para confirmar contra Stripe de verdad:

    python manage.py shell -c "
    import stripe
    from apps.payments.stripe_client import configurar_stripe
    configurar_stripe(); print('cuenta:', stripe.Account.retrieve().id)"
"""
from django.conf import settings
from django.core.checks import Error, register

# (ajuste, prefijo que le pone Stripe, codigo, como se llama en el dashboard).
# Vacio significa "esta funcion esta apagada" y es comportamiento documentado
# (sin llave, `crear-pago` responde 503), asi que solo se revisa lo que trae algo.
LLAVES_DE_STRIPE = (
    (
        'STRIPE_SECRET_KEY',
        'sk_',
        'payments.E001',
        'la llave secreta (Developers -> API keys)',
    ),
    (
        'STRIPE_WEBHOOK_SECRET',
        'whsec_',
        'payments.E002',
        'el signing secret del endpoint (Developers -> Webhooks)',
    ),
)


@register()
def revisar_llaves_de_stripe(app_configs, **kwargs):
    """Reporta las llaves de Stripe que no tienen el prefijo de su tipo.

    El mensaje **nunca incluye el valor**: un check que imprime la llave la deja
    escrita en el log del deploy, que es justo lo que no se quiere.
    """
    errores = []

    for ajuste, prefijo, codigo, de_donde_sale in LLAVES_DE_STRIPE:
        valor = getattr(settings, ajuste, '')
        if valor and not valor.startswith(prefijo):
            errores.append(Error(
                f'{ajuste} no empieza con "{prefijo}", asi que no es la llave que '
                f'esta variable espera.',
                hint=(
                    f'Parece una llave de Stripe capturada en la variable equivocada. '
                    f'En {ajuste} va {de_donde_sale}. Corrigela en el environment group '
                    f'de Render y redespliega. Ver docs/deploy/GO-LIVE.md, Fase 5.'
                ),
                id=codigo,
            ))

    return errores
