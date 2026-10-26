"""Sesion del admin: el sondeo de avisos no cuenta como actividad.

`SESSION_SAVE_EVERY_REQUEST = True` renueva la cookie de sesion en cada respuesta. El sondeo de `avisos.js` pregunta
cada 10 s sin que la persona haga nada, asi que una pestana olvidada abierta mantendria viva la sesion para siempre y
el limite de inactividad (`SESSION_COOKIE_AGE`) dejaria de existir. Estas rutas responden sin renovar la sesion.
"""
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers

RUTAS_DE_SONDEO = frozenset({'/admin/avisos/reservas-nuevas/'})


class SesionSinRenovarEnSondeo(SessionMiddleware):
    """El sondeo lee la sesion pero no la guarda ni renueva su cookie."""

    def process_response(self, request, response):
        if request.path_info in RUTAS_DE_SONDEO:
            patch_vary_headers(response, ('Cookie',))
            return response
        return super().process_response(request, response)
