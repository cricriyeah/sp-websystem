"""Nombre del backoffice segun el alcance de la cuenta autenticada."""

from . import scope


NOMBRE_PLATAFORMA = 'Sun Baja Experiences'


def nombre_backoffice(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return NOMBRE_PLATAFORMA

    empresa = scope.empresa_actual(request)
    return empresa.nombre if empresa is not None else NOMBRE_PLATAFORMA
