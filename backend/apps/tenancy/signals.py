# backend/apps/tenancy/signals.py
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import MembresiaEmpresa
from .roles import sincronizar_grupos_de_usuario

User = get_user_model()


@receiver(post_save, sender=MembresiaEmpresa)
def sincronizar_grupos_al_guardar_membresia(sender, instance, **kwargs):
    if instance.user_id:
        try:
            sincronizar_grupos_de_usuario(instance.user)
        except ObjectDoesNotExist:
            pass


@receiver(post_delete, sender=MembresiaEmpresa)
def sincronizar_grupos_al_borrar_membresia(sender, instance, **kwargs):
    # En post_delete el usuario puede haberse borrado ya (cascada):
    # atrapa User.DoesNotExist/usuario sin pk y sigue sin error.
    if instance.user_id:
        try:
            user = instance.user
            if user and getattr(user, 'pk', None):
                sincronizar_grupos_de_usuario(user)
        except (ObjectDoesNotExist, AttributeError):
            pass
