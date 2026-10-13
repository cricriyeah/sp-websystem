"""Permisos para la navegación lateral de Unfold (import perezoso de scope)."""


def puede_ver_finanzas(request) -> bool:
    """Acceso a finanzas: operador de plataforma o jefe de la empresa actual.

    Ya no basta con tener empresa (las vendedoras quedan excluidas): el usuario
    debe pertenecer al grupo Django 'Jefe'. La usan el menu lateral y las vistas
    de `apps.finance`, para que la regla no pueda diverger entre las dos.
    """
    from apps.tenancy import scope

    usuario = getattr(request, 'user', None)
    if usuario is None or usuario.is_anonymous:
        return False
    if scope.es_operador_plataforma(usuario):
        return True
    return scope.empresa_actual(request) is not None and usuario.groups.filter(name='Jefe').exists()


def es_operador(request) -> bool:
    from apps.tenancy import scope

    return scope.es_operador_plataforma(request.user)
