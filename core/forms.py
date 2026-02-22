"""
Formularios del Sistema de Gestión de Préstamos
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML, Field
from .models import Cliente, Prestamo, RutaCobro, TipoNegocio


class ClienteForm(forms.ModelForm):
    """Formulario para crear/editar clientes"""
    
    # Redefinir como CharField para aceptar formato con puntos de miles
    limite_credito = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg input-monto-formateado',
            'placeholder': 'Dejar vacío = sin límite (ilimitado)',
            'inputmode': 'numeric',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'dni', 'telefono', 'direccion', 
                  'referencia1_nombre', 'referencia1_telefono',
                  'referencia2_nombre', 'referencia2_telefono',
                  'tipo_negocio', 'tipo_comercio', 
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
            'dni': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'DNI',
                'inputmode': 'numeric',
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
            'referencia1_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre y parentesco (ej: Juan Pérez - Hermano)'
            }),
            'referencia1_telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono referencia 1',
                'type': 'tel',
                'inputmode': 'tel'
            }),
            'referencia2_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre y parentesco (ej: María López - Vecina)'
            }),
            'referencia2_telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono referencia 2',
                'type': 'tel',
                'inputmode': 'tel'
            }),
            'tipo_negocio': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tipo_comercio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción adicional del negocio'
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
        
        # Formatear el valor inicial de limite_credito con puntos de miles
        if self.instance and self.instance.pk and self.instance.limite_credito:
            from decimal import Decimal
            valor = int(self.instance.limite_credito)
            # Formatear con puntos de miles
            self.initial['limite_credito'] = '{:,}'.format(valor).replace(',', '.')
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nombre', css_class='col-6'),
                Column('apellido', css_class='col-6'),
            ),
            'dni',
            'telefono',
            'direccion',
            HTML('<hr class="my-3"><h6 class="text-muted mb-3"><i class="bi bi-people me-1"></i> Contactos de Referencia</h6>'),
            Row(
                Column('referencia1_nombre', css_class='col-7'),
                Column('referencia1_telefono', css_class='col-5'),
            ),
            Row(
                Column('referencia2_nombre', css_class='col-7'),
                Column('referencia2_telefono', css_class='col-5'),
            ),
            HTML('<hr class="my-3">'),
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
    
    def clean_limite_credito(self):
        """Limpiar y convertir límite de crédito con formato de puntos de miles"""
        limite = self.data.get('limite_credito', '0')
        if isinstance(limite, str):
            limite = limite.replace('.', '').replace(',', '.')
            if not limite:
                limite = '0'
        try:
            from decimal import Decimal
            return Decimal(limite)
        except:
            raise forms.ValidationError('Ingrese un monto válido')


class PrestamoForm(forms.ModelForm):
    """Formulario para crear préstamos"""
    
    # Redefinir como CharField para aceptar formato con puntos de miles
    monto_solicitado = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg input-monto-formateado',
            'placeholder': 'Monto solicitado',
            'inputmode': 'numeric',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = Prestamo
        fields = ['cliente', 'monto_solicitado', 'tasa_interes_porcentaje', 
                  'cuotas_pactadas', 'frecuencia', 'fecha_inicio', 'fecha_finalizacion', 'notas']
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-select form-select-lg'
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
            'fecha_finalizacion': forms.DateInput(attrs={
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
        # Fecha de finalización es opcional
        self.fields['fecha_finalizacion'].required = False
        self.fields['fecha_finalizacion'].help_text = 'Opcional. Dejar vacío para calcular automáticamente.'
        
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
            Row(
                Column('fecha_inicio', css_class='col-6'),
                Column('fecha_finalizacion', css_class='col-6'),
            ),
            HTML('''
                <div class="text-muted small mb-2" style="margin-top:-0.5rem;">
                    <i class="bi bi-info-circle me-1"></i>Si dejás vacía la fecha de finalización, se calcula automáticamente según la frecuencia y cantidad de cuotas.
                </div>
            '''),
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
    
    def clean_monto_solicitado(self):
        """Limpiar y convertir monto con formato de puntos de miles"""
        monto = self.data.get('monto_solicitado', '')
        if isinstance(monto, str):
            # Quitar puntos de miles y convertir coma decimal a punto
            monto = monto.replace('.', '').replace(',', '.')
        try:
            from decimal import Decimal
            return Decimal(monto)
        except:
            raise forms.ValidationError('Ingrese un monto válido')
    
    def clean(self):
        """Validar límite de crédito del cliente"""
        cleaned_data = super().clean()
        cliente = cleaned_data.get('cliente')
        monto = cleaned_data.get('monto_solicitado')
        
        if cliente and monto:
            maximo = cliente.maximo_prestable
            if maximo is not None and monto > maximo:
                from decimal import Decimal
                if maximo <= Decimal('0'):
                    raise forms.ValidationError(
                        f'El cliente {cliente.nombre_completo} no tiene crédito disponible. '
                        f'Deuda actual: ${cliente.credito_usado:,.0f}'.replace(',', '.')
                    )
                else:
                    raise forms.ValidationError(
                        f'El monto solicitado (${monto:,.0f}) excede el límite de crédito disponible '
                        f'para {cliente.nombre_completo}. Máximo prestable: ${maximo:,.0f}'.replace(',', '.')
                    )
        
        # Validar fecha de finalización si se proporcionó
        fecha_fin = cleaned_data.get('fecha_finalizacion')
        fecha_inicio = cleaned_data.get('fecha_inicio')
        frecuencia = cleaned_data.get('frecuencia')
        
        # Pago único requiere fecha de finalización obligatoria
        if frecuencia == 'PU' and not fecha_fin:
            self.add_error('fecha_finalizacion', 'Para pago único, debe indicar la fecha de vencimiento.')
        
        if fecha_fin and fecha_inicio:
            if fecha_fin <= fecha_inicio:
                self.add_error('fecha_finalizacion', 'La fecha de finalización debe ser posterior a la fecha de inicio.')
        
        # Pago único fuerza 1 cuota
        if frecuencia == 'PU':
            cleaned_data['cuotas_pactadas'] = 1
        
        return cleaned_data
    
    def save(self, commit=True):
        """Guardar préstamo marcando si la fecha de finalización fue manual"""
        instance = super().save(commit=False)
        if self.cleaned_data.get('fecha_finalizacion'):
            instance.fecha_finalizacion_manual = True
        else:
            instance.fecha_finalizacion_manual = False
        if commit:
            instance.save()
        return instance


class RenovacionPrestamoForm(forms.Form):
    """Formulario para renovar préstamos"""
    
    # Usar CharField para aceptar formato con puntos de miles
    nuevo_monto = forms.CharField(
        required=False,
        label='Nuevo Capital Adicional',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg input-monto-formateado',
            'placeholder': 'Capital adicional (0 si solo renueva deuda)',
            'inputmode': 'numeric',
            'autocomplete': 'off'
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
    
    fecha_finalizacion = forms.DateField(
        required=False,
        label='Fecha de Finalización',
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.saldo_pendiente = kwargs.pop('saldo_pendiente', 0)
        super().__init__(*args, **kwargs)
        self.fields['fecha_finalizacion'].help_text = 'Opcional. Si la completás, se calculan las cuotas automáticamente.'
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'nuevo_monto',
            Row(
                Column('nueva_tasa', css_class='col-6'),
                Column('nuevas_cuotas', css_class='col-6'),
            ),
            'nueva_frecuencia',
            'fecha_finalizacion',
            HTML('''
                <div class="text-muted small mb-2" style="margin-top:-0.5rem;">
                    <i class="bi bi-info-circle me-1"></i>Si completás la fecha de finalización, las cuotas se calculan automáticamente según la frecuencia.
                </div>
            '''),
            Div(
                Submit('submit', 'Renovar Préstamo', css_class='btn btn-warning btn-lg w-100 mt-3'),
                css_class='d-grid'
            )
        )
    
    def clean_nuevo_monto(self):
        """Limpiar y convertir monto con formato de puntos de miles"""
        monto = self.data.get('nuevo_monto', '0')
        if isinstance(monto, str):
            monto = monto.replace('.', '').replace(',', '.')
            if not monto:
                monto = '0'
        try:
            from decimal import Decimal
            return Decimal(monto)
        except:
            raise forms.ValidationError('Ingrese un monto válido')
    
    def clean(self):
        """Validar límite de crédito del cliente para renovación"""
        cleaned_data = super().clean()
        nuevo_monto = cleaned_data.get('nuevo_monto', 0) or 0
        
        if self.cliente and nuevo_monto > 0:
            from decimal import Decimal
            # El total nuevo sería el nuevo monto más el saldo pendiente
            total_renovacion = nuevo_monto + Decimal(str(self.saldo_pendiente))
            maximo = self.cliente.maximo_prestable
            
            # El máximo prestable ya considera la deuda actual, así que para renovación
            # sumamos el saldo pendiente (que se cancelará) al máximo
            maximo_para_renovacion = None
            if maximo is not None:
                maximo_para_renovacion = maximo + Decimal(str(self.saldo_pendiente))
            
            if maximo_para_renovacion is not None and nuevo_monto > maximo_para_renovacion:
                if maximo_para_renovacion <= Decimal('0'):
                    raise forms.ValidationError(
                        f'El cliente no tiene crédito disponible para capital adicional.'
                    )
                else:
                    raise forms.ValidationError(
                        f'El capital adicional (${nuevo_monto:,.0f}) excede el límite disponible. '
                        f'Máximo capital adicional: ${maximo_para_renovacion:,.0f}'.replace(',', '.')
                    )
        
        # Validar fecha de finalización
        fecha_fin = cleaned_data.get('fecha_finalizacion')
        if fecha_fin:
            from datetime import date
            hoy = date.today()
            if fecha_fin <= hoy:
                self.add_error('fecha_finalizacion', 'La fecha de finalización debe ser posterior a hoy.')
        
        return cleaned_data


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

