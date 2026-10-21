"""Nombre y logo del backoffice segun el alcance de la cuenta autenticada."""

from django.templatetags.static import static

from . import scope


NOMBRE_PLATAFORMA = 'Sun Baja Experiences'

# Logo de cada empresa (apps/tenancy/static/tenancy/branding/<slug>.webp): el jefe o la vendedora ven el de
# la suya en el menu lateral, en lugar de su nombre. Una empresa sin logo conserva su nombre.
EMPRESAS_CON_LOGO = frozenset({'sal-y-sol', 'transporte-la-paz', 'la-ventana-travel', 'piratas-adventures'})


def nombre_backoffice(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return NOMBRE_PLATAFORMA

    empresa = scope.empresa_actual(request)
    return empresa.nombre if empresa is not None else NOMBRE_PLATAFORMA


def logo_backoffice(request):
    """Logo del menu lateral: el de la empresa de la cuenta (o, si esa empresa aun no tiene logo, nada: se
    queda su nombre); el de Sun Baja Experience para el operador de la plataforma, el superusuario o quien
    aun no inicia sesion (negro en claro, blanco en oscuro)."""
    if request.user.is_authenticated and not request.user.is_superuser:
        empresa = scope.empresa_actual(request)
        if empresa is not None:
            if empresa.slug in EMPRESAS_CON_LOGO:
                return static(f'tenancy/branding/{empresa.slug}.webp')
            return None
    return {
        'light': static('tenancy/branding/sunbaja.svg'),
        'dark': static('tenancy/branding/sunbaja-blanco.svg'),
    }
