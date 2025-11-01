// Script de Prueba para Verificar el Tooltip del Visualizador 3D
// Ejecuta esto en la consola del navegador (F12) después de cargar el grafo

console.log('🔍 Verificando estado del tooltip...\n');

// 1. Verificar que el tooltip existe
const tooltip = document.querySelector('.graph-hover-tooltip');
if (tooltip) {
    console.log('✅ Tooltip encontrado:', tooltip);
    console.log('   - Display:', tooltip.style.display);
    console.log('   - Visibility:', tooltip.style.visibility);
    console.log('   - Opacity:', tooltip.style.opacity);
    console.log('   - Z-index:', tooltip.style.zIndex);
    console.log('   - Position:', tooltip.style.position);
    console.log('   - Left:', tooltip.style.left);
    console.log('   - Top:', tooltip.style.top);
    console.log('   - Border:', tooltip.style.border);
    console.log('   - Background:', tooltip.style.background);
} else {
    console.log('❌ Tooltip NO encontrado');
}

// 2. Verificar el contenedor
const container = document.getElementById('graph-plot');
if (container) {
    console.log('\n✅ Contenedor encontrado');
    console.log('   - Position:', window.getComputedStyle(container).position);
    console.log('   - Hijos:', container.children.length);
    
    // Listar todos los hijos
    Array.from(container.children).forEach((child, i) => {
        console.log(`   - Hijo ${i}:`, child.tagName, child.className);
    });
} else {
    console.log('\n❌ Contenedor NO encontrado');
}

// 3. Forzar mostrar tooltip de prueba
console.log('\n🧪 Intentando mostrar tooltip de prueba...');
if (tooltip) {
    tooltip.innerHTML = `
        <div style="font-weight: 700; color: #000; margin-bottom: 10px; font-size: 14px;">
            ✅ TOOLTIP DE PRUEBA
        </div>
        <div style="color: #333; font-size: 12px;">
            Si ves esto, el tooltip funciona!
        </div>
    `;
    tooltip.style.setProperty('left', '100px', 'important');
    tooltip.style.setProperty('top', '100px', 'important');
    tooltip.style.setProperty('display', 'block', 'important');
    tooltip.style.setProperty('visibility', 'visible', 'important');
    tooltip.style.setProperty('opacity', '1', 'important');
    
    console.log('✅ Tooltip de prueba mostrado en posición (100, 100)');
    console.log('   ⚠️ Si no lo ves, puede estar detrás de otro elemento');
    
    // Ocultar después de 3 segundos
    setTimeout(() => {
        tooltip.style.setProperty('display', 'none', 'important');
        console.log('🔄 Tooltip de prueba ocultado');
    }, 3000);
} else {
    console.log('❌ No se puede mostrar tooltip de prueba - elemento no existe');
}

// 4. Verificar canvas y su z-index
const canvas = container?.querySelector('canvas');
if (canvas) {
    console.log('\n✅ Canvas encontrado');
    console.log('   - Z-index:', canvas.style.zIndex);
    console.log('   - Position:', canvas.style.position);
}

console.log('\n📋 Resumen:');
console.log('   - Tooltip existe:', !!tooltip);
console.log('   - Contenedor existe:', !!container);
console.log('   - Canvas existe:', !!canvas);
console.log('\n💡 Si el tooltip de prueba NO apareció:');
console.log('   1. Verifica que estás en la pestaña correcta');
console.log('   2. Busca un cuadro blanco con borde naranja en (100, 100)');
console.log('   3. Puede estar detrás del canvas - revisa los z-index');
