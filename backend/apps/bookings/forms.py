from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.tenancy.models import Empresa


class AltaVendedoraForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    nombre = forms.CharField(max_length=150)
    codigo = forms.SlugField(
        max_length=30, help_text='Va en el link que le pasa a sus clientes: ?ref=<codigo>',
    )
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)

    def __init__(self, *args, es_operador=False, **kwargs):
        super().__init__(*args, **kwargs)
        if es_operador:
            self.fields['empresa'].required = True
        else:
            del self.fields['empresa']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese nombre de usuario.')
        return username

    def clean_password(self):
        password = self.cleaned_data['password']
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password
