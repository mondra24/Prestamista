/**
 * Sistema de Gestión de Préstamos - JavaScript
 * Funcionalidades AJAX para cobros en tiempo real
 */

// Configuración global
const CONFIG = {
    CSRF_TOKEN: null,
    // Formato de pesos argentinos: punto como separador de miles
    CURRENCY_FORMAT: new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    })
};

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Obtener CSRF token
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        CONFIG.CSRF_TOKEN = csrfInput.value;
    } else {
        // Obtener de las cookies
        CONFIG.CSRF_TOKEN = getCookie('csrftoken');
    }
    
    // Inicializar funciones
    initCobros();
    initCalculadoraPrestamo();
    initBusqueda();
    initFormateoMontos();
});

/**
 * Obtener cookie por nombre
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Formatear número con separador de miles argentino (punto) y decimales con coma
 * Ejemplo: 1234567.89 -> 1.234.567,89
 */
function formatNumber(num, decimals = 0) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    const number = parseFloat(num);
    
    // Redondear según decimales
    let rounded;
    if (decimals > 0) {
        rounded = number.toFixed(decimals);
    } else {
        rounded = Math.round(number).toString();
    }
    
    // Separar parte entera y decimal
    const parts = rounded.split('.');
    
    // Formatear parte entera con puntos como separadores de miles
    let intPart = parts[0];
    let formattedInt = '';
    for (let i = intPart.length - 1, count = 0; i >= 0; i--, count++) {
        if (count > 0 && count % 3 === 0) {
            formattedInt = '.' + formattedInt;
        }
        formattedInt = intPart[i] + formattedInt;
    }
    
    const decPart = parts[1] || '';
    
    // Usar coma para decimales (formato argentino)
    return decPart ? `${formattedInt},${decPart}` : formattedInt;
}

/**
 * Formatear moneda en pesos argentinos
 * Ejemplo: 1234567 -> $1.234.567
 * Ejemplo con decimales: 1234567.50 -> $1.234.567,50
 */
function formatCurrency(amount, decimals = 0) {
    return '$' + formatNumber(amount, decimals);
}

/**
 * Inicializar sistema de cobros AJAX
 */
function initCobros() {
    document.querySelectorAll('.btn-cobrar').forEach(btn => {
        btn.addEventListener('click', handleCobro);
    });
}

/**
 * Manejar cobro de cuota
 */
async function handleCobro(event) {
    event.preventDefault();
    const btn = event.currentTarget;
    const cuotaId = btn.dataset.cuotaId;
    const card = btn.closest('.cobro-card');
    
    // Evitar doble click
    if (btn.disabled) return;
    btn.disabled = true;
    
    // Mostrar loading
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    try {
        const response = await fetch(`/api/cobrar/${cuotaId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CONFIG.CSRF_TOKEN
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Feedback de éxito
            showToast('¡Pago registrado!', 'success');
            
            // Actualizar UI de la tarjeta
            card.classList.add('estado-pagado');
            card.classList.remove('estado-pendiente', 'estado-vencido');
            
            // Cambiar botón
            btn.innerHTML = '<i class="bi bi-check-lg"></i>';
            btn.classList.add('cobrado');
            
            // Animación
            card.classList.add('pulse');
            setTimeout(() => card.classList.remove('pulse'), 300);
            
            // Actualizar estadísticas con datos del servidor
            if (data.estadisticas) {
                updateStatsFromServer(data.estadisticas);
            }
            
            // Opcional: Ocultar tarjeta después de un momento
            setTimeout(() => {
                card.style.opacity = '0.5';
            }, 1000);
            
        } else {
            throw new Error(data.message || 'Error al procesar el pago');
        }
        
    } catch (error) {
        console.error('Error:', error);
        showToast(error.message, 'error');
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}

/**
 * Registrar pago parcial con opciones de manejo del restante
 */
async function registrarPagoParcial(cuotaId, monto, accionRestante = 'ignorar', fechaEspecial = null) {
    try {
        const body = { 
            monto: monto,
            accion_restante: accionRestante
        };
        
        if (accionRestante === 'especial' && fechaEspecial) {
            body.fecha_especial = fechaEspecial;
        }
        
        const response = await fetch(`/api/cobrar/${cuotaId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CONFIG.CSRF_TOKEN
            },
            body: JSON.stringify(body)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || `Pago de ${formatCurrency(monto)} registrado`, 'success');
            location.reload(); // Recargar para actualizar montos
        } else {
            throw new Error(data.message);
        }
        
    } catch (error) {
        showToast(error.message, 'error');
    }
}

/**
 * Mostrar modal de pago parcial con opciones
 */
function showPagoParcialModal(cuotaId, montoRestante, nombreCliente = '') {
    const modal = document.getElementById('modal-pago-parcial');
    if (!modal) return;
    
    // Asegurar que el monto es un número válido
    const montoNumerico = parseFloat(montoRestante) || 0;
    
    document.getElementById('pago-cuota-id').value = cuotaId;
    document.getElementById('pago-monto-max').value = montoNumerico;
    document.getElementById('pago-monto-max-label').textContent = formatCurrency(montoNumerico);
    document.getElementById('pago-monto').value = '';
    document.getElementById('pago-monto').placeholder = formatNumber(montoNumerico);
    
    // Resetear opciones
    const accionSelect = document.getElementById('pago-accion-restante');
    if (accionSelect) {
        accionSelect.value = 'ignorar';
        toggleFechaEspecial();
    }
    
    // Mostrar nombre del cliente si existe
    const clienteLabel = document.getElementById('pago-cliente-nombre');
    if (clienteLabel && nombreCliente) {
        clienteLabel.textContent = nombreCliente;
    }
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Limpiar label de monto formateado
    const montoLabel = document.getElementById('monto-formateado-label');
    if (montoLabel) {
        montoLabel.textContent = 'Ingrese el monto que el cliente pagará';
    }
}

/**
 * Parsear monto desde string formateado con puntos
 * Ejemplo: "1.234.567" -> 1234567
 */
function parsearMonto(montoString) {
    if (!montoString) return 0;
    // Quitar puntos de miles y convertir coma decimal a punto (si existe)
    const limpio = montoString.toString().replace(/\./g, '').replace(',', '.');
    return parseFloat(limpio) || 0;
}

/**
 * Formatear input de monto mientras el usuario escribe
 * Agrega puntos como separador de miles
 */
function formatearInputMonto(input) {
    // Obtener posición del cursor
    const cursorPos = input.selectionStart;
    const oldValue = input.value;
    const oldLength = oldValue.length;
    
    // Quitar todo excepto números
    let valor = input.value.replace(/[^\d]/g, '');
    
    // Si está vacío, dejarlo así
    if (!valor) {
        input.value = '';
        return;
    }
    
    // Formatear con puntos de miles
    input.value = formatNumber(parseInt(valor));
    
    // Ajustar posición del cursor
    const newLength = input.value.length;
    const diff = newLength - oldLength;
    const newPos = Math.max(0, cursorPos + diff);
    
    // Restaurar posición del cursor
    setTimeout(() => {
        input.setSelectionRange(newPos, newPos);
    }, 0);
}

/**
 * Actualizar etiqueta con monto formateado mientras el usuario escribe
 */
function actualizarMontoFormateado() {
    const input = document.getElementById('pago-monto');
    const label = document.getElementById('monto-formateado-label');
    
    if (!input || !label) return;
    
    const valor = parsearMonto(input.value);
    
    if (valor && valor > 0) {
        label.innerHTML = `<strong class="text-success">Cobrando: ${formatCurrency(valor)}</strong>`;
    } else {
        label.textContent = 'Ingrese el monto que el cliente pagará';
    }
}

/**
 * Toggle para mostrar/ocultar campo de fecha especial
 */
function toggleFechaEspecial() {
    const accion = document.getElementById('pago-accion-restante')?.value || 'ignorar';
    const fechaContainer = document.getElementById('fecha-especial-container');
    
    if (fechaContainer) {
        fechaContainer.style.display = accion === 'especial' ? 'block' : 'none';
        
        // Set fecha mínima a mañana
        const fechaInput = document.getElementById('pago-fecha-especial');
        if (fechaInput) {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            fechaInput.min = tomorrow.toISOString().split('T')[0];
            fechaInput.value = tomorrow.toISOString().split('T')[0];
        }
    }
}

/**
 * Confirmar pago parcial con opciones
 */
function confirmarPagoParcial() {
    const cuotaId = document.getElementById('pago-cuota-id').value;
    const montoMax = parseFloat(document.getElementById('pago-monto-max').value);
    const montoInput = document.getElementById('pago-monto').value;
    const monto = parsearMonto(montoInput);
    const accionRestante = document.getElementById('pago-accion-restante')?.value || 'ignorar';
    const fechaEspecial = document.getElementById('pago-fecha-especial')?.value || null;
    
    if (!monto || monto <= 0) {
        showToast('Ingrese un monto válido', 'error');
        return;
    }
    
    if (monto > montoMax) {
        showToast('El monto no puede ser mayor al pendiente', 'error');
        return;
    }
    
    // Si hay monto restante y seleccionó especial, validar fecha
    if (monto < montoMax && accionRestante === 'especial' && !fechaEspecial) {
        showToast('Seleccione una fecha para la cuota especial', 'error');
        return;
    }
    
    registrarPagoParcial(cuotaId, monto, accionRestante, fechaEspecial);
}

/**
 * Actualizar estadísticas desde respuesta del servidor
 */
function updateStatsFromServer(stats) {
    const totalCobradoEl = document.getElementById('total-cobrado-hoy');
    const cantidadCobrosEl = document.getElementById('cantidad-cobros-hoy');
    
    if (totalCobradoEl && stats.total_cobrado_hoy !== undefined) {
        // Usar formatCurrency para mostrar sin decimales
        totalCobradoEl.textContent = formatCurrency(stats.total_cobrado_hoy);
    }
    
    if (cantidadCobrosEl && stats.cantidad_cobros_hoy !== undefined) {
        cantidadCobrosEl.textContent = stats.cantidad_cobros_hoy;
    }
}

/**
 * Actualizar estadísticas del dashboard (fallback)
 */
function updateStats() {
    const totalCobradoEl = document.getElementById('total-cobrado-hoy');
    const cantidadCobrosEl = document.getElementById('cantidad-cobros-hoy');
    
    if (totalCobradoEl && cantidadCobrosEl) {
        // Incrementar contador
        const currentCount = parseInt(cantidadCobrosEl.textContent) || 0;
        cantidadCobrosEl.textContent = currentCount + 1;
        
        // Nota: El total se actualiza desde el servidor
    }
}

/**
 * Calculadora de préstamo en tiempo real
 */
function initCalculadoraPrestamo() {
    const montoInput = document.getElementById('id_monto_solicitado');
    const tasaInput = document.getElementById('id_tasa_interes_porcentaje');
    const cuotasInput = document.getElementById('id_cuotas_pactadas');
    const resumenDiv = document.getElementById('resumen-prestamo');
    
    if (!montoInput || !tasaInput || !cuotasInput || !resumenDiv) return;
    
    const calcular = () => {
        // Usar parsearMonto para manejar formato con puntos de miles
        const monto = parsearMonto(montoInput.value);
        const tasa = parseFloat(tasaInput.value) || 0;
        const cuotas = parseInt(cuotasInput.value) || 1;
        
        if (monto > 0) {
            const interes = monto * (tasa / 100);
            const total = monto + interes;
            const valorCuota = total / cuotas;
            
            document.getElementById('total-pagar').textContent = formatCurrency(total);
            document.getElementById('valor-cuota').textContent = formatCurrency(valorCuota);
            resumenDiv.style.display = 'block';
            
            // Validar límite de crédito
            validarLimiteCredito(monto);
        } else {
            resumenDiv.style.display = 'none';
        }
    };
    
    // No agregar listener a monto ya que se maneja en initFormateoMontos
    tasaInput.addEventListener('input', calcular);
    cuotasInput.addEventListener('input', calcular);
    
    // Calcular al cargar si hay valores
    calcular();
}

/**
 * Inicializar búsqueda en tiempo real
 */
function initBusqueda() {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    
    if (!searchInput || !searchResults) return;
    
    let timeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(timeout);
        const query = e.target.value.trim();
        
        if (query.length < 2) {
            searchResults.innerHTML = '';
            return;
        }
        
        timeout = setTimeout(() => {
            // Aquí se podría implementar búsqueda AJAX
            // Por ahora filtrar elementos existentes
            filterLocalResults(query);
        }, 300);
    });
}

/**
 * Filtrar resultados locales
 */
function filterLocalResults(query) {
    const items = document.querySelectorAll('.filtrable');
    const lowerQuery = query.toLowerCase();
    
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(lowerQuery)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

/**
 * Mostrar toast de notificación
 */
function showToast(message, type = 'info') {
    // Crear contenedor si no existe
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
    }
    
    // Colores según tipo
    const colors = {
        success: 'bg-success',
        error: 'bg-danger',
        warning: 'bg-warning',
        info: 'bg-info'
    };
    
    const icons = {
        success: 'bi-check-circle-fill',
        error: 'bi-exclamation-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };
    
    // Crear toast
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white ${colors[type]} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${icons[type]} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000
    });
    bsToast.show();
    
    // Remover del DOM después de ocultarse
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

/**
 * Confirmación antes de acciones importantes
 */
function confirmar(mensaje, callback) {
    if (confirm(mensaje)) {
        callback();
    }
}

/**
 * Vibración para feedback táctil (si está disponible)
 */
function vibrate(duration = 50) {
    if (navigator.vibrate) {
        navigator.vibrate(duration);
    }
}

/**
 * Agregar vibración a botones de cobro
 */
document.addEventListener('click', (e) => {
    if (e.target.closest('.btn-cobrar')) {
        vibrate(50);
    }
});

/**
 * Inicializar formateo de montos en inputs con clase .input-monto-formateado
 */
function initFormateoMontos() {
    const inputs = document.querySelectorAll('.input-monto-formateado');
    
    inputs.forEach(input => {
        // Formatear valor inicial si existe
        if (input.value) {
            const valor = parsearMonto(input.value);
            if (valor > 0) {
                input.value = formatNumber(valor);
            }
        }
        
        // Evento de input para formatear mientras se escribe
        input.addEventListener('input', function(e) {
            formatearInputMonto(this);
            
            // Disparar evento para actualizar calculadora si existe
            const montoInput = document.getElementById('id_monto_solicitado');
            if (this === montoInput) {
                actualizarCalculadoraPrestamo();
            }
        });
        
        // Evento de focus para seleccionar todo el texto
        input.addEventListener('focus', function() {
            setTimeout(() => this.select(), 50);
        });
    });
}

/**
 * Actualizar calculadora de préstamo con valores formateados
 */
function actualizarCalculadoraPrestamo() {
    const montoInput = document.getElementById('id_monto_solicitado');
    const tasaInput = document.getElementById('id_tasa_interes_porcentaje');
    const cuotasInput = document.getElementById('id_cuotas_pactadas');
    const resumenDiv = document.getElementById('resumen-prestamo');
    
    if (!montoInput || !tasaInput || !cuotasInput || !resumenDiv) return;
    
    const monto = parsearMonto(montoInput.value);
    const tasa = parseFloat(tasaInput.value) || 0;
    const cuotas = parseInt(cuotasInput.value) || 1;
    
    if (monto > 0) {
        const interes = monto * (tasa / 100);
        const total = monto + interes;
        const valorCuota = total / cuotas;
        
        document.getElementById('total-pagar').textContent = formatCurrency(total);
        document.getElementById('valor-cuota').textContent = formatCurrency(valorCuota);
        resumenDiv.style.display = 'block';
        
        // Validar límite de crédito si hay cliente seleccionado
        validarLimiteCredito(monto);
    } else {
        resumenDiv.style.display = 'none';
    }
}

/**
 * Validar límite de crédito en tiempo real
 */
function validarLimiteCredito(monto) {
    const selectCliente = document.getElementById('id_cliente');
    const alertaCredito = document.getElementById('alerta-credito');
    
    if (!selectCliente || !alertaCredito || typeof clientesData === 'undefined') return;
    
    const clienteId = selectCliente.value;
    if (!clienteId || !clientesData[clienteId]) return;
    
    const cliente = clientesData[clienteId];
    
    if (cliente.maximoPrestable !== null && monto > cliente.maximoPrestable) {
        document.getElementById('alerta-credito-texto').innerHTML = 
            `<strong>¡Atención!</strong> El monto ingresado ($${formatNumber(monto)}) excede el límite de crédito disponible ($${formatNumber(cliente.maximoPrestable)}).`;
        alertaCredito.classList.remove('d-none');
        alertaCredito.classList.remove('alert-warning');
        alertaCredito.classList.add('alert-danger');
    } else if (cliente.maximoPrestable !== null && monto > cliente.maximoPrestable * 0.8) {
        // Advertencia si está cerca del límite (80%)
        document.getElementById('alerta-credito-texto').innerHTML = 
            `El monto está cerca del límite de crédito disponible ($${formatNumber(cliente.maximoPrestable)}).`;
        alertaCredito.classList.remove('d-none');
        alertaCredito.classList.add('alert-warning');
        alertaCredito.classList.remove('alert-danger');
    } else {
        alertaCredito.classList.add('d-none');
    }
}
