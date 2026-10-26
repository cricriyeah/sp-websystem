"""Formularios de la recuperacion de contrasena (paso 1: correo; paso 2: correo, codigo y contrasena nueva)."""
from django import forms
from unfold.widgets import UnfoldAdminEmailInputWidget, UnfoldAdminPasswordWidget, UnfoldAdminTextInputWidget

LARGO_MAXIMO_CONTRASENA = 128  # tope contra una contrasena enorme que solo busca gastar CPU en el hasheo


class SolicitarForm(forms.Form):
    correo = forms.EmailField(
        label='Correo de tu cuenta', max_length=254,
        widget=UnfoldAdminEmailInputWidget(attrs={'autocomplete': 'email', 'autofocus': True}),
    )


class ConfirmarForm(forms.Form):
    correo = forms.EmailField(
        label='Correo de tu cuenta', max_length=254,
        widget=UnfoldAdminEmailInputWidget(attrs={'autocomplete': 'email'}),
    )
    codigo = forms.RegexField(
        label='Código de 6 dígitos', regex=r'^[0-9]{6}$', max_length=6, min_length=6,
        error_messages={'invalid': 'El código son 6 dígitos.'},
        widget=UnfoldAdminTextInputWidget(attrs={
            'autocomplete': 'one-time-code', 'inputmode': 'numeric', 'pattern': '[0-9]{6}', 'maxlength': '6',
        }),
    )
    password1 = forms.CharField(
        label='Contraseña nueva', max_length=LARGO_MAXIMO_CONTRASENA, strip=False,
        widget=UnfoldAdminPasswordWidget(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Repite la contraseña nueva', max_length=LARGO_MAXIMO_CONTRASENA, strip=False,
        widget=UnfoldAdminPasswordWidget(attrs={'autocomplete': 'new-password'}),
    )

    def clean(self):
        datos = super().clean()
        if datos.get('password1') and datos.get('password2') and datos['password1'] != datos['password2']:
            self.add_error('password2', 'Las dos contraseñas no coinciden.')
        return datos
