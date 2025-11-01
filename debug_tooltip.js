// ========================================
// 🔍 SCRIPT DE DEBUG PARA EL VISUALIZADOR
// ========================================
// Copia y pega esto en la consola del navegador (F12)

console.log('=== VERIFICACIÓN DEL TOOLTIP ===');

// 1. Buscar el elemento del tooltip
const tooltip = document.getElementById('graph-hover-tooltip-element');
console.log('1. ¿Tooltip existe?', !!tooltip);

if (tooltip) {
    console.log('2. Tooltip encontrado:', tooltip);
    console.log('3. Padre del tooltip:', tooltip.parentElement);
    console.log('4. Z-index:', tooltip.style.zIndex);
    console.log('5. Display:', tooltip.style.display);
    console.log('6. Position:', tooltip.style.position);
    console.log('7. Background:', tooltip.style.background);
    console.log('8. Border:', tooltip.style.border);
    
    // Probar forzar visibilidad
    console.log('\n=== FORZANDO VISIBILIDAD ===');
    tooltip.style.display = 'block';
    tooltip.style.left = '100px';
    tooltip.style.top = '100px';
    tooltip.style.zIndex = '999999';
    tooltip.innerHTML = '<div style="padding: 20px; background: white; border: 3px solid red;">🔴 TOOLTIP DE PRUEBA - Si ves esto, el tooltip funciona!</div>';
    console.log('✅ Tooltip forzado a mostrarse en (100, 100)');
    console.log('   Si NO lo ves, hay un problema de CSS o z-index');
} else {
    console.log('❌ ERROR: Tooltip no encontrado en el DOM');
    console.log('   Buscar cualquier tooltip:');
    const allTooltips = document.querySelectorAll('.graph-hover-tooltip');
    console.log('   Tooltips encontrados:', allTooltips.length);
    allTooltips.forEach((t, i) => {
        console.log(`   Tooltip ${i}:`, t);
    });
}

// 2. Verificar el contenedor del grafo
console.log('\n=== VERIFICACIÓN DEL CONTENEDOR ===');
const graphPlot = document.getElementById('graph-plot');
console.log('1. ¿Contenedor existe?', !!graphPlot);
if (graphPlot) {
    console.log('2. Position:', window.getComputedStyle(graphPlot).position);
    console.log('3. Z-index:', window.getComputedStyle(graphPlot).zIndex);
    console.log('4. Hijos:', graphPlot.children.length);
    Array.from(graphPlot.children).forEach((child, i) => {
        console.log(`   Hijo ${i}:`, child.tagName, child.className, 'z-index:', child.style.zIndex);
    });
}

// 3. Verificar el canvas
console.log('\n=== VERIFICACIÓN DEL CANVAS ===');
const canvas = graphPlot?.querySelector('canvas');
console.log('1. ¿Canvas existe?', !!canvas);
if (canvas) {
    console.log('2. Z-index:', canvas.style.zIndex);
    console.log('3. Position:', canvas.style.position);
}

console.log('\n=== FIN DE LA VERIFICACIÓN ===');
console.log('Ahora pasa el mouse sobre un nodo y busca los mensajes 🎯');
