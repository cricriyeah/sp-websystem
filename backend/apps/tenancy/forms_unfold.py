from django import forms
from unfold.widgets import (
    UnfoldAdminPasswordWidget, UnfoldAdminSelectWidget, UnfoldAdminTextInputWidget,
)


class EstiloUnfoldMixin:
    """Formularios propios (fuera del ModelAdmin) con los controles del panel.

    Los widgets de Django no traen las clases de Unfold y su CSS base deja los campos sin
    borde ni fondo: el formulario se ve como etiquetas sueltas. Llamar a
    `_aplicar_estilo_unfold()` al final del `__init__`."""

    def _aplicar_estilo_unfold(self):
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.PasswordInput):
                campo.widget = UnfoldAdminPasswordWidget()
            elif isinstance(widget, forms.Select) and not isinstance(widget, forms.SelectMultiple):
                campo.widget = UnfoldAdminSelectWidget(choices=campo.choices)
            elif type(widget) is forms.TextInput:
                campo.widget = UnfoldAdminTextInputWidget()
