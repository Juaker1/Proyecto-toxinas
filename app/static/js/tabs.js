document.addEventListener("DOMContentLoaded", () => {
    // Elementos de pestañas
    const tabButtons = document.querySelectorAll(".tab-button");
    const tabContents = document.querySelectorAll(".tab-content");
    
    // Referencia al contenedor de propiedades del grafo
    const propertiesContainer = document.querySelector(".graph-properties-container");
    if (propertiesContainer) {
        propertiesContainer.style.display = 'none';
    }
    
    // Función para cambiar pestañas
    function changeTab(tabId) {
        // Desactivar todas las pestañas
        tabButtons.forEach(button => button.classList.remove("active"));
        tabContents.forEach(content => content.classList.remove("active"));
        
        // Activar la pestaña seleccionada
        document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
        document.getElementById(tabId).classList.add("active");
        
        // Mostrar/ocultar el contenedor de propiedades según la pestaña
        if (propertiesContainer) {
            propertiesContainer.style.display = tabId === 'graph-view' ? 'block' : 'none';
        }
        
        // Si cambiamos a la vista de grafo, actualizar la visualización
        if (tabId === 'graph-view') {
            // Obtener la proteína seleccionada actualmente
            const groupSelect = document.getElementById("groupSelect");
            const proteinSelect = document.getElementById("proteinSelect");
            
            if (window.triggerGraphUpdate) {
                console.log("Actualizando visualización de grafo al cambiar a pestaña");
                window.triggerGraphUpdate(groupSelect.value, proteinSelect.value);
            }
        }
    }
    
    // Asignar eventos a los botones de pestaña
    tabButtons.forEach(button => {
        button.addEventListener("click", () => {
            const tabId = button.getAttribute("data-tab");
            changeTab(tabId);
        });
    });
    
    // Exponer la función para usarla en otros scripts
    window.changeTab = changeTab;
});