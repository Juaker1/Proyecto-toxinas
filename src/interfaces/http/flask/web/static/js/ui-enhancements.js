/**
 * ANIMACIONES Y MEJORAS INTERACTIVAS
 * Efectos visuales útiles para mejorar la experiencia de usuario
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeAnimations();
    initializeToggleControls();
    initializeFormEnhancements();
    initializeLoadingStates();
});

/**
 * Inicializa animaciones de entrada para elementos
 */
function initializeAnimations() {
    // Animación de fade-in para secciones
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeIn 0.6s ease-out forwards';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observar cards y secciones
    document.querySelectorAll('.card, .view-panel, .stat-card').forEach(el => {
        el.style.opacity = '0';
        observer.observe(el);
    });
}

/**
 * Maneja controles de toggle (mostrar/ocultar)
 */
function initializeToggleControls() {
    // Toggle switches personalizados
    document.querySelectorAll('.toggle-switch').forEach(toggle => {
        toggle.addEventListener('click', function() {
            this.classList.toggle('active');
            const checkbox = this.querySelector('input[type="checkbox"]') || 
                           document.getElementById(this.getAttribute('data-target'));
            if (checkbox) {
                checkbox.checked = this.classList.contains('active');
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });
    
    // Checkboxes personalizados
    document.querySelectorAll('.custom-checkbox').forEach(checkbox => {
        const input = checkbox.querySelector('input[type="checkbox"]') ||
                     checkbox.previousElementSibling;
        
        checkbox.addEventListener('click', function() {
            this.classList.toggle('checked');
            if (input) {
                input.checked = this.classList.contains('checked');
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
        
        // Sincronizar estado inicial
        if (input && input.checked) {
            checkbox.classList.add('checked');
        }
    });
    
    // Botones de toggle con icono rotatorio
    document.querySelectorAll('.analysis-toggle-btn, .toggle-table-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.toggle('open');
            const icon = this.querySelector('.toggle-icon');
            if (icon) {
                icon.style.transform = this.classList.contains('open') ? 
                    'rotate(180deg)' : 'rotate(0deg)';
            }
        });
    });
}

/**
 * Mejoras para formularios
 */
function initializeFormEnhancements() {
    // Validación visual en tiempo real
    document.querySelectorAll('.form-control, .form-select, .filter-input').forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value && this.checkValidity()) {
                this.style.borderColor = 'var(--secondary-500)';
                setTimeout(() => {
                    this.style.borderColor = '';
                }, 1000);
            }
        });
        
        // Efecto de focus
        input.addEventListener('focus', function() {
            this.parentElement.style.transform = 'translateY(-2px)';
            this.parentElement.style.transition = 'transform 0.2s ease';
        });
        
        input.addEventListener('blur', function() {
            this.parentElement.style.transform = '';
        });
    });
    
    // Select mejorado con animación
    document.querySelectorAll('.form-select, .family-select').forEach(select => {
        select.addEventListener('change', function() {
            this.style.transform = 'scale(1.02)';
            setTimeout(() => {
                this.style.transform = '';
            }, 200);
        });
    });
}

/**
 * Manejo de estados de carga
 */
function initializeLoadingStates() {
    // Función para mostrar loading
    window.showLoading = function(containerId, message = 'Cargando...') {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const loadingHTML = `
            <div class="loading-state" style="animation: fadeIn 0.3s ease-in;">
                <div class="spinner spinner-lg"></div>
                <p class="loading-text">${message}</p>
            </div>
        `;
        
        container.innerHTML = loadingHTML;
    };
    
    // Función para ocultar loading
    window.hideLoading = function(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const loadingState = container.querySelector('.loading-state');
        if (loadingState) {
            loadingState.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                loadingState.remove();
            }, 300);
        }
    };
}

/**
 * Función para mostrar notificaciones toast
 */
window.showToast = function(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        z-index: 10000;
        min-width: 300px;
        max-width: 500px;
        animation: slideDown 0.3s ease-out;
        box-shadow: var(--shadow-xl);
    `;
    
    const icons = {
        info: 'ℹ️',
        success: '✅',
        warning: '⚠️',
        error: '❌'
    };
    
    toast.innerHTML = `
        <span class="alert-icon">${icons[type] || icons.info}</span>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideUp 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
    }, duration);
};

/**
 * Función para confirmar acciones
 */
window.confirmAction = function(message, onConfirm, onCancel) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.3s ease-in;
    `;
    
    const modal = document.createElement('div');
    modal.className = 'card';
    modal.style.cssText = `
        max-width: 500px;
        animation: slideDown 0.3s ease-out;
    `;
    
    modal.innerHTML = `
        <div class="card-header">
            <h3 class="card-title" style="margin: 0;">⚠️ Confirmar Acción</h3>
        </div>
        <div class="card-body">
            <p>${message}</p>
        </div>
        <div class="card-footer" style="display: flex; gap: var(--space-3); justify-content: flex-end;">
            <button class="btn btn-ghost" id="cancel-btn">Cancelar</button>
            <button class="btn btn-primary" id="confirm-btn">Confirmar</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    const confirmBtn = modal.querySelector('#confirm-btn');
    const cancelBtn = modal.querySelector('#cancel-btn');
    
    const closeModal = () => {
        overlay.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => overlay.remove(), 300);
    };
    
    confirmBtn.addEventListener('click', () => {
        closeModal();
        if (onConfirm) onConfirm();
    });
    
    cancelBtn.addEventListener('click', () => {
        closeModal();
        if (onCancel) onCancel();
    });
    
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal();
            if (onCancel) onCancel();
        }
    });
};

/**
 * Animación de progreso para botones
 */
window.addButtonProgress = function(buttonElement, promise) {
    const originalHTML = buttonElement.innerHTML;
    const originalWidth = buttonElement.offsetWidth;
    
    buttonElement.disabled = true;
    buttonElement.style.width = originalWidth + 'px';
    buttonElement.innerHTML = `
        <div class="spinner spinner-sm"></div>
        <span>Procesando...</span>
    `;
    
    promise.finally(() => {
        buttonElement.disabled = false;
        buttonElement.style.width = '';
        buttonElement.innerHTML = originalHTML;
    });
};

/**
 * Scroll suave a elemento
 */
window.smoothScrollTo = function(elementId, offset = 100) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const targetPosition = element.getBoundingClientRect().top + window.pageYOffset - offset;
    
    window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
    });
};

// Agregar animación fadeOut al CSS si no existe
if (!document.querySelector('#fadeOutAnimation')) {
    const style = document.createElement('style');
    style.id = 'fadeOutAnimation';
    style.textContent = `
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}
