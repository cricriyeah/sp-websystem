"""Alta de una Empresa nueva en un solo paso, y su lista de pendientes.

Antes eran ocho saltos entre el admin, Stripe y la consola. Aqui se hace en una
transaccion lo que vive dentro del sistema (Sede opcional, Empresa, cuenta del jefe
y su membresia) y `estado_de_empresa` dice que falta de lo que no se puede hacer
desde aqui (Stripe y el catalogo), con el enlace a donde se arregla.
"""
from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.urls import reverse
from django.utils.text import slugify

from .forms_unfold import EstiloUnfoldMixin
from .models import Empresa, MembresiaEmpresa, Sede
from .usuarios import crear_usuario_con_rol


class AltaEmpresaForm(EstiloUnfoldMixin, forms.Form):
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.filter(activo=True), required=False, label='Sede existente',
        help_text='La ciudad donde opera. Si es una ciudad nueva, deja esto vacío y escribe su nombre abajo.',
    )
    sede_nueva = forms.CharField(max_length=150, required=False, label='O sede nueva')
    nombre = forms.CharField(max_length=150, label='Nombre de la empresa')
    slug = forms.SlugField(
        max_length=150, required=False, label='Identificador en la URL',
        help_text='Vacío = se arma con el nombre. No se puede cambiar después: el webhook de Stripe depende de él.',
    )
    correos_aviso = forms.CharField(
        max_length=300, required=False, label='Correos de aviso',
        help_text='A quién avisar de cada reserva pagada. Varias direcciones separadas por coma.',
    )
    jefe_usuario = forms.CharField(max_length=150, label='Usuario del jefe')
    jefe_nombre = forms.CharField(max_length=150, label='Nombre del jefe')
    jefe_password = forms.CharField(widget=forms.PasswordInput, label='Contraseña inicial del jefe')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilo_unfold()

    def clean(self):
        datos = super().clean()
        if bool(datos.get('sede')) == bool((datos.get('sede_nueva') or '').strip()):
            raise ValidationError('Elige una sede existente o escribe el nombre de una nueva (una de las dos).')
        return datos

    def clean_slug(self):
        return self._slug_libre(self.cleaned_data['slug'], Empresa, 'la empresa')

    def clean_jefe_usuario(self):
        usuario = self.cleaned_data['jefe_usuario']
        if User.objects.filter(username=usuario).exists():
            raise ValidationError('Ya existe una cuenta con ese usuario.')
        return usuario

    def clean_jefe_password(self):
        clave = self.cleaned_data['jefe_password']
        try:
            validate_password(clave)
        except ValidationError as exc:
            raise ValidationError(exc.messages)
        return clave

    def clean_correos_aviso(self):
        # Mismo criterio que Empresa.clean(): un correo mal escrito no debe llegar a la base.
        try:
            Empresa(correos_aviso=self.cleaned_data['correos_aviso']).clean()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict['correos_aviso'])
        return self.cleaned_data['correos_aviso']

    def _slug_libre(self, slug, modelo, de_quien):
        if slug and modelo.objects.filter(slug=slug).exists():
            raise ValidationError(f'Ya hay {de_quien} con ese identificador.')
        return slug


def dar_de_alta_empresa(datos):
    """Crea Sede (si es nueva), Empresa, cuenta del jefe y membresia. Devuelve la Empresa.

    Si los grupos de roles aun no existen (primera empresa del sistema) corre
    `setup_roles`, que es idempotente: ya no hay que acordarse de hacerlo en la consola.
    """
    with transaction.atomic():
        sede = datos.get('sede')
        if sede is None:
            nombre_sede = datos['sede_nueva'].strip()
            sede = Sede.objects.create(nombre=nombre_sede, slug=_slug_unico(Sede, nombre_sede))

        empresa = Empresa.objects.create(
            sede=sede,
            nombre=datos['nombre'],
            slug=datos.get('slug') or _slug_unico(Empresa, datos['nombre']),
            correos_aviso=datos.get('correos_aviso', ''),
        )
        crear_usuario_con_rol(
            username=datos['jefe_usuario'],
            password=datos['jefe_password'],
            nombre=datos['jefe_nombre'],
            rol=MembresiaEmpresa.Rol.JEFE,
            empresa=empresa,
        )
    return empresa


def _slug_unico(modelo, texto):
    base = slugify(texto) or 'empresa'
    slug, n = base, 2
    while modelo.objects.filter(slug=slug).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug


def estado_de_empresa(empresa):
    """Lista de pendientes de una Empresa: [{texto, hecho, url, accion}].

    Solo lee. Corre bajo el alcance del operador de plataforma (es su pantalla),
    asi que los conteos del catalogo ven la Empresa completa.
    """
    from apps.bookings.models import Vendedora
    from apps.fleet.models import Embarcacion, Servicio, Vehiculo

    def cambiar_empresa(): return reverse('admin:tenancy_empresa_change', args=[empresa.pk])

    llaves = [empresa.stripe_secret_key, empresa.stripe_publishable_key, empresa.stripe_webhook_secret]
    membresias = empresa.membresias.all()
    servicios = Servicio.objects.filter(empresa=empresa, activo=True)
    hay_flota = (Embarcacion.objects.filter(empresa=empresa, activa=True).exists()
                 or Vehiculo.objects.filter(empresa=empresa, activo=True).exists())

    return [
        {'texto': 'Empresa creada', 'hecho': True, 'url': cambiar_empresa(), 'accion': 'Ver'},
        {'texto': 'Tiene un jefe con cuenta',
         'hecho': membresias.filter(rol=MembresiaEmpresa.Rol.JEFE).exists(),
         'url': reverse('admin:tenancy_membresiaempresa_add'), 'accion': 'Agregar membresía'},
        {'texto': 'Llaves de Stripe puestas (secreta, publicable y secreto del webhook)',
         'hecho': all(llaves), 'url': cambiar_empresa(), 'accion': 'Poner llaves'},
        {'texto': 'Tiene al menos una vendedora',
         'hecho': Vendedora.objects.filter(empresa=empresa, activo=True).exists(),
         'url': reverse('admin:bookings_user_alta_usuario'), 'accion': 'Dar de alta vendedora'},
        {'texto': 'Tiene al menos un servicio activo en el catálogo',
         'hecho': servicios.exists(), 'url': reverse('admin:fleet_servicio_add'), 'accion': 'Agregar servicio'},
        {'texto': 'Tiene pangas o vehículos activos',
         'hecho': hay_flota, 'url': reverse('admin:fleet_embarcacion_add'), 'accion': 'Agregar panga'},
    ]


def url_del_webhook(empresa, request):
    """La URL que se pega en el Dashboard de Stripe de esta Empresa."""
    return request.build_absolute_uri(reverse('stripe-webhook', args=[empresa.slug]))
