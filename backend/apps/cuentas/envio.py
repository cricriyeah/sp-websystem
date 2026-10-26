"""Envio de correos de la recuperacion fuera de la peticion.

Si la respuesta esperara a Resend (~300 ms) solo cuando la cuenta existe, el tiempo de respuesta
delataria que la cuenta existe. El envio sale en un hilo daemon, ya despues del commit.

Limite aceptado: si Render recicla el proceso mientras el hilo corre, el correo se pierde; la persona
vuelve a pedirlo pasado el minuto de espera. Una cola externa (Celery, Redis) seria infraestructura
nueva para un flujo de muy baja frecuencia.
"""
import logging
import sys
import threading

from django.db import connections

logger = logging.getLogger(__name__)


def _es_prueba():
    # Misma convencion que `settings.APARTADO_MINUTOS`: bajo `manage.py test` todo es sincrono para poder
    # inspeccionar el resultado sin carreras.
    return 'test' in sys.argv


def _ejecutar(funcion, args, cerrar_conexion):
    try:
        funcion(*args)
    except Exception as exc:  # excepcion deliberada: un fallo de envio nunca debe tumbar el hilo ni la peticion
        # Solo la clase: el mensaje o una traza con las variables locales podrian llevar el codigo.
        logger.error('Fallo el envio del correo de recuperacion (%s)', type(exc).__name__)
    finally:
        if cerrar_conexion:
            # El hilo abre su propia conexion a la base; si no se cierra se queda abierta hasta que Postgres la corte.
            connections.close_all()


def despachar(funcion, *args):
    """Corre `funcion(*args)` en un hilo daemon. Sincrono bajo `manage.py test`. Devuelve el hilo (o None)."""
    if _es_prueba():
        _ejecutar(funcion, args, cerrar_conexion=False)
        return None
    hilo = threading.Thread(
        target=_ejecutar, args=(funcion, args, True), name='cuentas-envio', daemon=True,
    )
    hilo.start()
    return hilo
