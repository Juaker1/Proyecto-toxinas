/**
 * Test para validar que el hover del panel acoplado funciona correctamente.
 * Ejecutar en la consola del navegador después de cargar el gráfico.
 */

function testHoverUpdate() {
    const renderer = window.graphRenderer; // asumir que está disponible globalmente
    if (!renderer) {
        console.error('graphRenderer no encontrado en window');
        return;
    }

    if (!renderer.dock) {
        console.error('dock panel no existe');
        return;
    }

    console.log('✓ Renderer encontrado');
    console.log('✓ Dock panel encontrado');
    console.log('  Dock display:', renderer.dock.style.display);
    console.log('  Dock visibility:', renderer.dock.style.visibility);
    console.log('  Dock z-index:', renderer.dock.style.zIndex);

    // Simular un hover manual
    if (renderer.graphData && renderer.graphData.nodes.length > 0) {
        const testNode = renderer.graphData.nodes[0];
        renderer.updateDockPanel(testNode, 0);
        console.log('✓ updateDockPanel llamado con nodo 0');
        console.log('  Dock Header:', renderer.dockHeaderTitle.textContent);
        console.log('  Dock Body HTML (first 100 chars):', renderer.dockBody.innerHTML.substring(0, 100));
        console.log('  Dock ahora visible?', renderer.dock.offsetHeight > 0);
    }
}

// Ejecutar prueba
testHoverUpdate();
