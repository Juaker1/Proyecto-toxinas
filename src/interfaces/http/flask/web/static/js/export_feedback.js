class ExportFeedbackManager {
    constructor() {
        this.initializeHTML();
        this.currentModal = null;
        this.toastCounter = 0;
        

    }

    initializeHTML() {
        // Crear container para toasts si no existe
        if (!document.getElementById('toast-container')) {
            const toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        // Crear modal de exportación si no existe
        if (!document.getElementById('export-modal')) {
            const modal = document.createElement('div');
            modal.id = 'export-modal';
            modal.className = 'export-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-icon" id="modal-icon"><i class="fas fa-chart-bar"></i></div>
                    <div class="modal-title" id="modal-title">Generando archivo CSV</div>
                    <div class="modal-subtitle" id="modal-subtitle">Procesando datos de toxinas...</div>
                    <div class="modal-progress">
                        <div class="progress-bar" id="progress-bar"></div>
                    </div>
                    <div class="modal-details" id="modal-details">
                        Calculando métricas de centralidad y propiedades topológicas
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
    }

    showExportModal(config = {}) {
        const modal = document.getElementById('export-modal');
        const modalIcon = document.getElementById('modal-icon');
        const modalTitle = document.getElementById('modal-title');
        const modalSubtitle = document.getElementById('modal-subtitle');
        const modalDetails = document.getElementById('modal-details');

        // Configurar contenido del modal
    modalIcon.innerHTML = `<i class="${config.iconClass || 'fas fa-chart-bar'}"></i>`;
        modalTitle.textContent = config.title || 'Generando archivo CSV';
        modalSubtitle.textContent = config.subtitle || 'Procesando datos de toxinas...';
        modalDetails.textContent = config.details || 'Calculando métricas de centralidad y propiedades topológicas';

        // Mostrar modal con animación
        modal.classList.add('show');
        this.currentModal = modal;

        // Animar barra de progreso
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.animation = 'none';
        setTimeout(() => {
            progressBar.style.animation = 'progressAnimation 3s ease-in-out infinite';
        }, 100);

        return modal;
    }

    hideExportModal() {
        const modal = document.getElementById('export-modal');
        if (modal) {
            modal.classList.remove('show');
            this.currentModal = null;
        }
    }

    showToast(type, title, message, duration = 5000) {
        const toastContainer = document.getElementById('toast-container');
        const toastId = `toast-${this.toastCounter++}`;
        
        const iconMap = {
            success: 'fas fa-check-circle',
            error: 'fas fa-times-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-header">
                <span class="toast-icon"><i class="${iconMap[type] || 'fas fa-info-circle'}"></i></span>
                <span class="toast-title">${title}</span>
                <button class="toast-close" onclick="exportFeedback.hideToast('${toastId}')">&times;</button>
            </div>
            <div class="toast-message">${message}</div>
        `;

        toastContainer.appendChild(toast);

        // Mostrar toast con animación
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        // Auto-ocultar después del tiempo especificado
        if (duration > 0) {
            setTimeout(() => {
                this.hideToast(toastId);
            }, duration);
        }

        return toastId;
    }
    

    hideToast(toastId) {
        const toast = document.getElementById(toastId);
        if (toast) {
            toast.classList.add('hide');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 400);
        }
    }

    // Métodos específicos para cada tipo de exportación
    startIndividualExport(toxinName) {
        return this.showExportModal({
            iconClass: 'fas fa-dna',
            title: 'Exportando Toxina Individual',
            subtitle: `Procesando: ${toxinName}`,
            details: 'Calculando centralidades de residuos individuales y propiedades estructurales'
        });
    }

    startFamilyExport(familyName, toxinCount) {
        return this.showExportModal({
            iconClass: 'fas fa-chart-line',
            title: 'Exportando Familia Completa',
            subtitle: `Procesando familia: ${familyName}`,
            details: `Analizando ${toxinCount} toxinas de la familia con métricas topológicas + IC₅₀`
        });
    }

    startWTComparison(wtFamily) {
        return this.showExportModal({
            iconClass: 'fas fa-microscope',
            title: 'Comparación WT vs Referencia',
            subtitle: `Comparando: ${wtFamily} vs hwt4_Hh2a_WT`,
            details: 'Calculando diferencias topológicas entre toxina WT y estructura de referencia'
        });
    }

    completeExport(type, details = {}) {
        this.hideExportModal();

        let title, message;

        switch (type) {
            case 'individual':
                title = '¡Exportación Individual Completada!';
                message = `XLSX generado exitosamente para la toxina ${details.toxinName || 'seleccionada'}. El archivo incluye métricas de centralidad y propiedades topológicas de todos los residuos.`;
                break;

            case 'family':
                title = '¡Dataset Familiar Generado!';
                message = `Dataset completo de la familia ${details.familyName || 'seleccionada'} listo. Incluye ${details.residueCount || 'múltiples'} residuos con métricas topológicas y valores IC₅₀ normalizados.`;
                break;

            case 'wt-comparison':
                title = '¡Comparación WT Completada!';
                message = `Análisis comparativo entre ${details.wtFamily || 'toxina WT'} y referencia hwt4_Hh2a_WT finalizado.`;
                break;

            default:
                title = '¡Exportación Completada!';
                message = 'El archivo XLSX ha sido generado exitosamente y está listo para descarga.';
        }

        return this.showToast('success', title, message, 6000);
    }

    showError(errorMessage, context = '') {
        this.hideExportModal();
        
    const title = 'Error en Exportación';
        const message = context 
            ? `Error ${context}: ${errorMessage}` 
            : `Se produjo un error durante la exportación: ${errorMessage}`;

        return this.showToast('error', title, message, 8000);
    }

    showWarning(warningMessage) {
    const title = 'Advertencia';
        return this.showToast('warning', title, warningMessage, 5000);
    }

    showInfo(infoMessage) {
    const title = 'Información';
        return this.showToast('info', title, infoMessage, 4000);
    }
}

// Instancia global del manager
window.exportFeedback = new ExportFeedbackManager();