from django.db import models


class TipoServicio(models.TextChoices):
    PESCA = 'pesca', 'Pesca deportiva'
    PASEO = 'paseo', 'Paseo / Tour'
    HOSPEDAJE = 'hospedaje', 'Hospedaje'
    BAJO_DEMANDA = 'bajo_demanda', 'Bajo demanda'


class EstrategiaCupo(models.TextChoices):
    POR_RECURSO_DIA = 'por_recurso_dia', 'Por recurso por día'
    POR_NOCHE = 'por_noche', 'Por noche'
    BAJO_DEMANDA = 'bajo_demanda', 'Bajo demanda'


class EstrategiaPrecio(models.TextChoices):
    POR_GRUPO = 'por_grupo', 'Por grupo'
    POR_PERSONA = 'por_persona', 'Por persona'
    TARIFA_FIJA = 'tarifa_fija', 'Tarifa fija'
    POR_NOCHE = 'por_noche', 'Por noche'


class ModoOcupacion(models.TextChoices):
    EXCLUSIVO = 'exclusivo', 'Exclusivo'
    COMPARTIDO = 'compartido', 'Compartido'
