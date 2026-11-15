"""En que idioma se le escribe al cliente: español o ingles.

El idioma se decide una vez por correo y lo leen todas las piezas que arman el cuerpo
(`services`, `plantilla`, los modulos de cada correo) sin pasarlo de mano en mano: quien
manda envuelve el armado en `with en_idioma(idioma_de(reserva)):` y cada texto se escribe
como `tr('en español', 'in English')`. Fuera de ese bloque todo sale en español, que es lo
que ya salia antes de que existiera el ingles.

De donde sale el idioma de una reserva (`Reserva.idioma_cliente`, `Orden.idioma_cliente`):

1. `idioma`: el del sitio en el que compro (`/es` o `/en`), o el que corrigio la vendedora.
2. Si esta vacio (venta a mano, reserva anterior a este campo): la lada del telefono. Sin
   lada o con +52, español; cualquier otra, ingles (`bookings.telefono.idioma_por_telefono`).

Los avisos internos a la empresa no pasan por aqui: siempre van en español.
"""
from contextlib import contextmanager
from contextvars import ContextVar

IDIOMAS = ('es', 'en')
_actual = ContextVar('idioma_del_correo', default='es')


def idioma_actual():
    return _actual.get()


@contextmanager
def en_idioma(codigo):
    marca = _actual.set(codigo if codigo in IDIOMAS else 'es')
    try:
        yield
    finally:
        _actual.reset(marca)


def tr(es, en):
    """El texto en el idioma del correo que se esta armando."""
    return en if _actual.get() == 'en' else es


def idioma_de(objeto):
    """`es` o `en` para una reserva o una orden (o lo que tenga `idioma_cliente`)."""
    codigo = getattr(objeto, 'idioma_cliente', '') or ''
    return codigo if codigo in IDIOMAS else 'es'


def en_catalogo(objeto, campo='nombre'):
    """El texto de catalogo en el idioma del correo: `<campo>_en` si existe y no esta vacio."""
    if objeto is None:
        return ''
    if _actual.get() == 'en':
        ingles = (getattr(objeto, f'{campo}_en', '') or '').strip()
        if ingles:
            return ingles
    return getattr(objeto, campo, '') or ''
