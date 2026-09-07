"""Permisos para la navegación lateral de Unfold (import perezoso de scope)."""


def puede_ver_finanzas(request) -> bool:
    from apps.tenancy import scope

    return (
        scope.es_operador_plataforma(request.user)
        or scope.empresa_actual(request) is not None
    )


def es_operador(request) -> bool:
    from apps.tenancy import scope

    return scope.es_operador_plataforma(request.user)
