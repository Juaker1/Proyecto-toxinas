/**
 * Script de validación para verificar que el panel de información (dock) funciona correctamente.
 * 
 
 */

console.clear();
console.log('%c=== VALIDACIÓN DEL PANEL DE INFORMACIÓN ===', 'font-size:16px; color:#FF6600; font-weight:bold');

function validateHoverSystem() {
    if (!window.graphRenderer) {
        console.error('❌ graphRenderer no encontrado. Asegúrate de que la página está cargada.');
        return;
    }

    const renderer = window.graphRenderer;
    
    console.log('\n%c📊 Estado del Renderer:', 'color:#0066ff; font-weight:bold');
    console.log('  ✓ Renderer encontrado');
    
    if (!renderer.dock) {
        console.error('  ❌ Panel acoplado (dock) no existe');
        return;
    }
    console.log('  ✓ Panel acoplado existe');

    // Verificar visibilidad
    const dockDisplay = window.getComputedStyle(renderer.dock).display;
    const dockVisibility = window.getComputedStyle(renderer.dock).visibility;
    const dockZIndex = window.getComputedStyle(renderer.dock).zIndex;
    
    console.log('\n%c🎨 Estilos del Panel:', 'color:#0066ff; font-weight:bold');
    console.log(`  Display: ${dockDisplay} ${dockDisplay === 'flex' ? '✓' : '❌'}`);
    console.log(`  Visibility: ${dockVisibility} ${dockVisibility === 'visible' ? '✓' : '❌'}`);
    console.log(`  Z-index: ${dockZIndex} (debe ser alto: 10001)`);

    // Verificar datos
    console.log('\n%c📈 Datos del Gráfico:', 'color:#0066ff; font-weight:bold');
    if (renderer.graphData && renderer.graphData.nodes) {
        console.log(`  Nodos: ${renderer.graphData.nodes.length}`);
        console.log(`  Aristas: ${renderer.graphData.edges.length}`);
    } else {
        console.warn('  ⚠️  No hay datos de gráfico cargados aún');
    }

    // Intentar actualizar el panel manualmente
    console.log('\n%c🧪 Prueba Manual:', 'color:#0066ff; font-weight:bold');
    if (renderer.graphData && renderer.graphData.nodes.length > 0) {
        const testNode = renderer.graphData.nodes[0];
        renderer.updateDockPanel(testNode, 0);
        console.log(`  ✓ Panel actualizado con: "${testNode.label}"`);
        console.log(`  → Título: "${renderer.dockHeaderTitle.textContent}"`);
        console.log(`  → Contenido renderizado: ${renderer.dockBody.innerHTML.length} caracteres`);
        
        const isVisible = renderer.dock.offsetHeight > 0;
        console.log(`  → Panel visible en pantalla: ${isVisible ? '✓ Sí' : '❌ No'}`);
        
        if (isVisible) {
            console.log('\n%c✅ ÉXITO: El panel funciona correctamente.', 'color:green; font-weight:bold; font-size:14px');
            console.log('Ahora pasa el mouse sobre los nodos en el gráfico.');
        } else {
            console.log('\n%c⚠️  El panel no es visible. Posibles causas:', 'color:orange; font-weight:bold');
            console.log('  - CSS oculto en el contenedor padre');
            console.log('  - Overflow hidden en el contenedor');
            console.log('  - Z-index insuficiente');
        }
    } else {
        console.warn('  ⚠️  Carga datos del gráfico primero');
    }

    // Instrucciones finales
    console.log('\n%c📋 Próximos Pasos:', 'color:#0066ff; font-weight:bold');
    console.log('  1. Pasa el mouse sobre cualquier nodo del gráfico');
    console.log('  2. Deberías ver el panel blanco/naranja actualizarse');
    console.log('  3. Haz clic en 📌 para fijar el panel');
    console.log('  4. Haz clic en 📋 para copiar la información');
    console.log('  5. Haz clic en ✖ para cerrar');

    // Agregar listener temporal para debug
    console.log('\n%c🔍 Monitoreando eventos de hover...', 'color:#0066ff; font-weight:bold');
    const originalUpdate = renderer.updateDockPanel.bind(renderer);
    let callCount = 0;
    renderer.updateDockPanel = function(node, index) {
        callCount++;
        if (callCount <= 5) { // Mostrar solo los primeros 5
            console.log(`  [${callCount}] Hover en: "${node.label}"`);
        }
        return originalUpdate(node, index);
    };
}

validateHoverSystem();

console.log('\n%c✨ Validación completada. Ve el navegador para ver el gráfico.', 'color:green; font-style:italic');
