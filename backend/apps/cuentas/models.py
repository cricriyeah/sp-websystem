"""Recuperacion de contrasena por codigo al correo (ver backend/CLAUDE.md, «Recuperacion de contrasena»).

Los dos modelos son por usuario y **sin empresa**: no entran al guardarrail de RLS (`tests_rls.py`) y
quien recupera su contrasena todavia no tiene alcance de empresa.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class CodigoRecuperacion(models.Model):
    """El codigo vigente de un usuario. Pedir otro lo **sobrescribe** (uno por usuario).

    Nunca guarda el codigo: solo su HMAC, atado al hash de la contrasena vigente (ver `seguridad.py`).
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='codigo_recuperacion'
    )
    codigo_hash = models.CharField(max_length=64)
    creado_en = models.DateTimeField(default=timezone.now)
    vence_en = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
    consumido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'codigo de recuperacion'
        verbose_name_plural = 'codigos de recuperacion'

    def __str__(self):
        # Sin el hash: un repr con el HMAC no sirve de nada y no hay por que dejarlo en una traza.
        return f'Codigo de recuperacion de usuario {self.usuario_id}'


class EventoRecuperacion(models.Model):
    """Bitacora de cada solicitud y confirmacion, y la base de los limites de uso.

    Los limites (por correo, por IP, global) se cuentan aqui y no en el cache: el cache de produccion
    es de archivos y `incr` no es atomico entre los procesos de gunicorn. **Nunca lleva el codigo.**
    """

    SOLICITUD = 'solicitud'
    CONFIRMACION = 'confirmacion'
    TIPOS = [(SOLICITUD, 'Solicitud'), (CONFIRMACION, 'Confirmacion')]

    creado_en = models.DateTimeField(default=timezone.now, db_index=True)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    # Cadena corta y fija (enviado, sin_cuenta, limite_correo, exito, codigo_incorrecto...): nunca texto libre.
    resultado = models.CharField(max_length=30)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    # HMAC del correo TECLEADO (exista o no): asi el limite por correo no distingue cuentas y la
    # bitacora no guarda direcciones en claro.
    correo_hash = models.CharField(max_length=64, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'evento de recuperacion'
        verbose_name_plural = 'eventos de recuperacion'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.tipo}:{self.resultado} {self.creado_en:%Y-%m-%d %H:%M}'
