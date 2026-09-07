"""Núcleo de funciones puras de cupo y disponibilidad (sin dependencias de base de datos)."""
import itertools

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
        if tope is not None and len(grupos) + 1 > tope:
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

    Una fecha sin entrada en `topes_por_fecha` se trata como «sin tope de
    conteo» (`None`), no como tope 0: el default 0 marcaba LLENO cualquier dia
    que el adaptador no hubiera rellenado explicitamente.
    """
    resultado = {}
    for fecha in fechas:
        grupos = grupos_por_fecha.get(fecha, [])
        capacidades = capacidades_por_fecha.get(fecha, [])
        tope = topes_por_fecha.get(fecha)
        resultado[fecha] = motivo_sin_lugar(personas, grupos, capacidades, tope, modo=modo)
    return resultado


def validar_rango(fecha_inicio, fecha_fin):
    """Un rango de ocupacion valido tiene `fecha_fin` estrictamente posterior a
    `fecha_inicio` (intervalo semi-abierto de al menos una noche). Devuelve el
    mensaje de error o None.
    """
    if fecha_fin is None or fecha_inicio is None:
        return None
    if fecha_fin <= fecha_inicio:
        return 'La fecha de fin debe ser posterior a la fecha de inicio.'
    return None


def rango_traslapa(ini1, fin1, ini2, fin2) -> bool:
    """Verifica si dos intervalos semi-abiertos [ini1, fin1) e [ini2, fin2) se traslapan.

    En semántica de hospedaje:
    [checkin_1, checkout_1) no colisiona con [checkin_2, checkout_2) si checkout_1 <= checkin_2.
    Dos rangos válidos traslapan si y solo si max(ini1, ini2) < min(fin1, fin2).
    """
    if ini1 >= fin1 or ini2 >= fin2:
        return False
    return max(ini1, ini2) < min(fin1, fin2)


def recursos_disponibles_en_rango(recursos_con_ocupaciones, fecha_inicio, fecha_fin):
    """Filtra los recursos que no tienen ninguna ocupación traslapada en [fecha_inicio, fecha_fin).

    `recursos_con_ocupaciones`: lista de (recurso_id, capacidad, [(o_ini, o_fin), ...]).
    Devuelve lista de (recurso_id, capacidad) de los recursos que están completamente libres.
    """
    libres = []
    for recurso_id, capacidad, ocupaciones in recursos_con_ocupaciones:
        traslapado = any(
            rango_traslapa(fecha_inicio, fecha_fin, o_ini, o_fin)
            for o_ini, o_fin in ocupaciones
        )
        if not traslapado:
            libres.append((recurso_id, capacidad))
    return libres


def elegir_recursos(libres: list[tuple[int, int]], personas: int, cantidad: int = 1) -> list[int] | None:
    """`libres` = [(recurso_id, capacidad), ...]. Devuelve los ids de `cantidad`
    recursos cuyo total de capacidad >= personas, prefiriendo los más chicos que
    alcanzan (menos desperdicio). None si no se puede.
    """
    if len(libres) < cantidad:
        return None

    candidatos = []
    for combo in itertools.combinations(libres, cantidad):
        cap_total = sum(c for _, c in combo)
        if cap_total >= personas:
            ids = sorted(r_id for r_id, _ in combo)
            desperdicio = cap_total - personas
            candidatos.append((desperdicio, ids))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (item[0], item[1]))
    return candidatos[0][1]
