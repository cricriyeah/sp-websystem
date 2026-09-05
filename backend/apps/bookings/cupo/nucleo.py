"""Núcleo de funciones puras de cupo y disponibilidad (sin dependencias de base de datos)."""

MOTIVO_LLENO = 'lleno'
MOTIVO_SIN_PANGA = 'sin_panga'
MOTIVO_SIN_LUGAR = 'sin_lugar'

MODO_EXCLUSIVO = 'exclusivo'
MODO_COMPARTIDO = 'compartido'


def caben(grupos, capacidades):
    """¿Hay forma de darle a cada grupo un recurso donde quepa en modo exclusivo?

    Las dos listas deben llegar ordenadas de mayor a menor.

    Se emparejan de mayor a menor: el grupo más grande con el recurso más grande. Si
    a algún grupo le toca un recurso más chico que él, no hay reparto posible — y no
    lo hay con ningún otro orden, porque cualquier reparto válido tendría que darle
    a ese grupo un recurso al menos igual de grande, y todos los de arriba ya están
    ocupados por grupos aún mayores.
    """
    if len(grupos) > len(capacidades):
        return False
    return all(g <= c for g, c in zip(grupos, capacidades))


def caben_compartido(grupos, capacidad_maxima):
    """¿Caben los grupos en un recurso en modo compartido?

    En modo compartido, múltiples reservas/grupos suman personas contra la
    capacidad máxima del recurso (suma simple sin emparejamiento por tamaño).
    """
    return sum(grupos) <= capacidad_maxima


def motivo_sin_lugar(personas, grupos, capacidades, tope, modo=MODO_EXCLUSIVO):
    """Por qué no entra un grupo de `personas` más, o None si sí entra.

    `grupos` son los tamaños ya vendidos de ese día/tramo, sin el nuevo.
    `capacidades` es la lista de capacidades (ordenada desc para exclusivo) o
    un número entero representando la capacidad total.
    `tope` es el límite de reservas o cupo del día.
    `modo`: MODO_EXCLUSIVO ('exclusivo') o MODO_COMPARTIDO ('compartido').

    Es el núcleo puro del cupo: no toca la base de datos.
    """
    if modo == MODO_EXCLUSIVO:
        if len(grupos) + 1 > tope:
            return MOTIVO_LLENO
        caps = list(capacidades)
        if not caben(sorted([*grupos, personas], reverse=True), caps):
            return MOTIVO_SIN_PANGA
        return None

    if modo == MODO_COMPARTIDO:
        if tope is not None and len(grupos) + 1 > tope:
            return MOTIVO_LLENO

        cap_total = sum(capacidades) if isinstance(capacidades, (list, tuple)) else capacidades
        if sum(grupos) + personas > cap_total:
            return MOTIVO_SIN_LUGAR
        return None

    raise ValueError(f'Modo de ocupación desconocido: {modo}')


def ocupacion_por_rango(fechas, grupos_por_fecha, capacidades_por_fecha, topes_por_fecha, personas, modo=MODO_EXCLUSIVO):
    """Calcula el motivo de no disponibilidad para cada fecha de un rango dado.

    Devuelve un diccionario {fecha: None | MOTIVO_LLENO | MOTIVO_SIN_PANGA | MOTIVO_SIN_LUGAR}.
    """
    resultado = {}
    for fecha in fechas:
        grupos = grupos_por_fecha.get(fecha, [])
        capacidades = capacidades_por_fecha.get(fecha, [])
        tope = topes_por_fecha.get(fecha, 0)
        resultado[fecha] = motivo_sin_lugar(personas, grupos, capacidades, tope, modo=modo)
    return resultado
