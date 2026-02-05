"""
Formularios del Sistema de Gestión de Préstamos
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML, Field
from .models import Cliente, Prestamo, RutaCobro, TipoNegocio


class ClienteForm(forms.ModelForm):
    """Formulario para crear/editar clientes"""
    
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'telefono', 'direccion', 'tipo_negocio', 'tipo_comercio', 
                  'limite_credito', 'ruta', 'dia_pago_preferido', 'categoria', 'estado', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nombre',
                'autocomplete': 'off'
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Apellido',
                'autocomplete': 'off'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Teléfono',
                'type': 'tel',
                'inputmode': 'tel'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Dirección completa',
                'rows': 2
            }),
            'tipo_negocio': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tipo_comercio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción adicional del negocio'
            }),
            'limite_credito': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Límite individual (0 = usar límite de categoría)',
                'inputmode': 'decimal',
                'min': '0',
                'step': '0.01'
            }),
            'ruta': forms.Select(attrs={
                'class': 'form-select'
            }),
            'dia_pago_preferido': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Lunes, Viernes'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Notas adicionales (opcional)',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ruta'].queryset = RutaCobro.objects.filter(activa=True)
        self.fields['ruta'].required = False
        self.fields['tipo_negocio'].queryset = TipoNegocio.objects.filter(activo=True)
        self.fields['tipo_negocio'].required = False
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nombre', css_class='col-6'),
                Column('apellido', css_class='col-6'),
            ),
            'telefono',
            'direccion',
            Row(
                Column('tipo_negocio', css_class='col-6'),
                Column('tipo_comercio', css_class='col-6'),
            ),
            Row(
                Column('limite_credito', css_class='col-6'),
                Column('ruta', css_class='col-6'),
            ),
            'dia_pago_preferido',
            Row(
                Column('categoria', css_class='col-6'),
                Column('estado', css_class='col-6'),
            ),
            'notas',
            Div(
                Submit('submit', 'Guardar', css_class='btn btn-success btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )


class PrestamoForm(forms.ModelForm):
    """Formulario para crear préstamos"""
    
    class Meta:
        model = Prestamo
        fields = ['cliente', 'monto_solicitado', 'tasa_interes_porcentaje', 
                  'cuotas_pactadas', 'frecuencia', 'fecha_inicio', 'notas']
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'monto_solicitado': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Monto solicitado',
                'inputmode': 'decimal',
                'min': '1',
                'step': '0.01'
            }),
            'tasa_interes_porcentaje': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '% de interés',
                'inputmode': 'decimal',
                'min': '0',
                'max': '100',
                'step': '0.01'
            }),
            'cuotas_pactadas': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Número de cuotas',
                'inputmode': 'numeric',
                'min': '1'
            }),
            'frecuencia': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control form-control-lg',
                'type': 'date'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Notas adicionales (opcional)',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar clientes activos
        self.fields['cliente'].queryset = Cliente.objects.filter(estado='AC')
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'cliente',
            Row(
                Column('monto_solicitado', css_class='col-6'),
                Column('tasa_interes_porcentaje', css_class='col-6'),
            ),
            Row(
                Column('cuotas_pactadas', css_class='col-6'),
                Column('frecuencia', css_class='col-6'),
            ),
            'fecha_inicio',
            HTML('''
                <div class="alert alert-info mt-3" id="resumen-prestamo" style="display:none;">
                    <h6 class="mb-2"><i class="bi bi-calculator"></i> Resumen del Préstamo</h6>
                    <div class="row">
                        <div class="col-6">
                            <small class="text-muted">Total a pagar:</small>
                            <div class="fw-bold fs-5" id="total-pagar">$0.00</div>
                        </div>
                        <div class="col-6">
                            <small class="text-muted">Valor cuota:</small>
                            <div class="fw-bold fs-5" id="valor-cuota">$0.00</div>
                        </div>
                    </div>
                </div>
            '''),
            'notas',
            Div(
                Submit('submit', 'Crear Préstamo', css_class='btn btn-success btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )


class RenovacionPrestamoForm(forms.Form):
    """Formulario para renovar préstamos"""
    
    nuevo_monto = forms.DecimalField(
        max_digits=12, 
        decimal_places=2,
        min_value=0,
        label='Nuevo Capital Adicional',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Capital adicional (0 si solo renueva deuda)',
            'inputmode': 'decimal',
            'min': '0',
            'step': '0.01'
        })
    )
    
    nueva_tasa = forms.DecimalField(
        max_digits=5, 
        decimal_places=2,
        min_value=0,
        max_value=100,
        label='Nueva Tasa de Interés (%)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '% de interés',
            'inputmode': 'decimal',
            'min': '0',
            'max': '100',
            'step': '0.01'
        })
    )
    
    nuevas_cuotas = forms.IntegerField(
        min_value=1,
        label='Número de Nuevas Cuotas',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Número de cuotas',
            'inputmode': 'numeric',
            'min': '1'
        })
    )
    
    nueva_frecuencia = forms.ChoiceField(
        choices=Prestamo.Frecuencia.choices,
        label='Nueva Frecuencia',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'nuevo_monto',
            Row(
                Column('nueva_tasa', css_class='col-6'),
                Column('nuevas_cuotas', css_class='col-6'),
            ),
            'nueva_frecuencia',
            Div(
                Submit('submit', 'Renovar Préstamo', css_class='btn btn-warning btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )


class UsuarioForm(forms.Form):
    """Formulario para crear nuevos usuarios"""
    from .models import PerfilUsuario
    
    username = forms.CharField(
        max_length=150,
        label='Nombre de Usuario',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Nombre de usuario',
            'autocomplete': 'off'
        })
    )
    
    first_name = forms.CharField(
        max_length=150,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Nombre'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Apellido'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Contraseña'
        })
    )
    
    password_confirm = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirmar contraseña'
        })
    )
    
    rol = forms.ChoiceField(
        choices=PerfilUsuario.Rol.choices,
        label='Rol',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg'
        })
    )
    
    telefono = forms.CharField(
        max_length=20,
        label='Teléfono',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Teléfono (opcional)'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'username',
            Row(
                Column('first_name', css_class='col-6'),
                Column('last_name', css_class='col-6'),
            ),
            'email',
            Row(
                Column('password', css_class='col-6'),
                Column('password_confirm', css_class='col-6'),
            ),
            Row(
                Column('rol', css_class='col-6'),
                Column('telefono', css_class='col-6'),
            ),
            Div(
                Submit('submit', 'Crear Usuario', css_class='btn btn-success btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )
    
    def clean_username(self):
        from django.contrib.auth.models import User
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya existe.')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        
        return cleaned_data


class UsuarioEditForm(forms.Form):
    """Formulario para editar usuarios existentes"""
    from .models import PerfilUsuario
    
    first_name = forms.CharField(
        max_length=150,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Nombre'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Apellido'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    
    password = forms.CharField(
        label='Nueva Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Dejar vacío para no cambiar'
        })
    )
    
    password_confirm = forms.CharField(
        label='Confirmar Nueva Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirmar nueva contraseña'
        })
    )
    
    rol = forms.ChoiceField(
        choices=PerfilUsuario.Rol.choices,
        label='Rol',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg'
        })
    )
    
    telefono = forms.CharField(
        max_length=20,
        label='Teléfono',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Teléfono (opcional)'
        })
    )
    
    activo = forms.BooleanField(
        label='Usuario Activo',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='col-6'),
                Column('last_name', css_class='col-6'),
            ),
            'email',
            Row(
                Column('password', css_class='col-6'),
                Column('password_confirm', css_class='col-6'),
            ),
            Row(
                Column('rol', css_class='col-6'),
                Column('telefono', css_class='col-6'),
            ),
            'activo',
            Div(
                Submit('submit', 'Guardar Cambios', css_class='btn btn-success btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password != password_confirm:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        
        return cleaned_data

