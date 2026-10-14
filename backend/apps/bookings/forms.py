from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection

from apps.bookings.models import Vendedora
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa

User = get_user_model()


class AltaUsuarioForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label='Usuario',
        help_text='Nombre de usuario para iniciar sesión.',
    )
    nombre = forms.CharField(
        max_length=150,
        label='Nombre completo',
        help_text='Nombre y apellido de la persona.',
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        label='Contraseña',
        help_text='Contraseña segura para la cuenta.',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        label='Confirmar contraseña',
        help_text='Vuelve a escribir la contraseña.',
    )
    rol = forms.ChoiceField(label='Rol', required=False)
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.none(),
        label='Empresa',
        required=False,
    )
    codigo = forms.SlugField(
        max_length=30,
        required=False,
        label='Código de vendedora',
        help_text='Va en el link que le pasa a sus clientes: ?ref=<codigo>',
    )

    def __init__(self, *args, es_operador=False, empresa_fija=None, **kwargs):
        self.es_operador = es_operador
        self.empresa_fija = empresa_fija
        super().__init__(*args, **kwargs)

        if self.es_operador:
            self.fields['rol'].choices = [
                (MembresiaEmpresa.Rol.JEFE, 'Jefe'),
                (MembresiaEmpresa.Rol.VENDEDORA, 'Vendedora'),
            ]
            self.fields['rol'].required = True
            self.fields['empresa'].queryset = Empresa.objects.all()
            self.fields['empresa'].required = True
        else:
            self.fields['rol'].choices = [
                (MembresiaEmpresa.Rol.VENDEDORA, 'Vendedora'),
            ]
            self.fields['rol'].initial = MembresiaEmpresa.Rol.VENDEDORA
            self.fields['rol'].required = False
            if self.empresa_fija:
                self.fields['empresa'].queryset = Empresa.objects.filter(pk=self.empresa_fija.pk)
                self.fields['empresa'].initial = self.empresa_fija
            else:
                self.fields['empresa'].queryset = Empresa.objects.all()
            self.fields['empresa'].disabled = True
            self.fields['empresa'].required = False

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese nombre de usuario.')
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise forms.ValidationError(exc.messages)
        return password

    def clean_empresa(self):
        if not self.es_operador:
            return self.empresa_fija
        empresa = self.cleaned_data.get('empresa')
        if not empresa:
            raise forms.ValidationError('Debes seleccionar una empresa.')
        return empresa

    def clean_rol(self):
        rol_submitted = self.cleaned_data.get('rol') or self.data.get('rol')
        if not self.es_operador:
            if rol_submitted and str(rol_submitted).strip().upper() not in ('VENDEDORA',):
                raise forms.ValidationError('Solo puedes dar de alta vendedoras.')
            return MembresiaEmpresa.Rol.VENDEDORA
        if not rol_submitted:
            raise forms.ValidationError('Debes seleccionar un rol.')
        return rol_submitted

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')

        rol = cleaned_data.get('rol')
        codigo = (cleaned_data.get('codigo') or '').strip()
        empresa = cleaned_data.get('empresa')

        if rol == MembresiaEmpresa.Rol.VENDEDORA or rol == 'Vendedora':
            if not codigo:
                self.add_error('codigo', 'El código de vendedora es obligatorio.')
            elif empresa:
                actual = getattr(connection, 'alcance_actual', None)
                if actual is None:
                    with scope.con_empresa(empresa):
                        if Vendedora.objects.filter(empresa=empresa, codigo=codigo).exists():
                            self.add_error('codigo', 'Ya existe una vendedora con ese código en esta empresa.')
                else:
                    if Vendedora.objects.filter(empresa=empresa, codigo=codigo).exists():
                        self.add_error('codigo', 'Ya existe una vendedora con ese código en esta empresa.')
        else:
            cleaned_data['codigo'] = None

        return cleaned_data


class AltaVendedoraForm(AltaUsuarioForm):
    """Alias retrocompatible con el formulario previo AltaVendedoraForm."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'rol' in self.fields:
            self.fields['rol'].initial = MembresiaEmpresa.Rol.VENDEDORA
