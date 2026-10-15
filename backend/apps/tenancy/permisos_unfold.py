"""Permisos para la navegación lateral de Unfold (import perezoso de scope)."""


def puede_ver_finanzas(request) -> bool:
    """Acceso a finanzas: operador de plataforma o jefe de la empresa actual.

    Ya no basta con tener empresa (las vendedoras quedan excluidas): el usuario
    debe tener rol JEFE en la empresa activa (membresía). La usan el menu lateral y las vistas
    de `apps.finance`, para que la regla no pueda diverger entre las dos.
    """
    from apps.tenancy import scope

    usuario = getattr(request, 'user', None)
    if usuario is None or usuario.is_anonymous:
        return False
    if scope.es_operador_plataforma(usuario):
        return True
    return scope.es_jefe_actual(request)


def es_operador(request) -> bool:
    from apps.tenancy import scope

    return scope.es_operador_plataforma(request.user)
