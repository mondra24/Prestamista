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
    document.getElementById('pago-monto').max = montoNumerico;
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
 * Actualizar etiqueta con monto formateado mientras el usuario escribe
 */
function actualizarMontoFormateado() {
    const input = document.getElementById('pago-monto');
    const label = document.getElementById('monto-formateado-label');
    
    if (!input || !label) return;
    
    const valor = parseFloat(input.value);
    
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
    const monto = parseFloat(document.getElementById('pago-monto').value);
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
        const monto = parseFloat(montoInput.value) || 0;
        const tasa = parseFloat(tasaInput.value) || 0;
        const cuotas = parseInt(cuotasInput.value) || 1;
        
        if (monto > 0) {
            const interes = monto * (tasa / 100);
            const total = monto + interes;
            const valorCuota = total / cuotas;
            
            document.getElementById('total-pagar').textContent = formatCurrency(total);
            document.getElementById('valor-cuota').textContent = formatCurrency(valorCuota);
            resumenDiv.style.display = 'block';
        } else {
            resumenDiv.style.display = 'none';
        }
    };
    
    montoInput.addEventListener('input', calcular);
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
