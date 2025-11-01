/**
 * Molstar Graph Renderer
 * WebGL-optimized 3D graph visualization using Mol* infrastructure
 * Replaces Plotly for sub-second rendering of dense molecular graphs
 */

class MolstarGraphRenderer {
    constructor(containerElement) {
        this.container = containerElement;
        this.canvas = null;
        this.ctx = null;
        this.graphData = null;
        // Node state: selectedNode (CLICK), hoveredNode (MOUSE OVER)
        this.selectedNode = null; // nodo seleccionado con CLICK (muestra conexiones en panel)
        this.hoveredNode = null; // nodo bajo el cursor (solo resalta colores)
        this.camera = {
            rotation: { x: 0.3, y: 0.3 },
            zoom: 1,
            distance: 150,
            target: { x: 0, y: 0, z: 0 }
        };
        this.isDragging = false;
        this.lastMouse = { x: 0, y: 0 };
        this.initialZoom = 1;
        this.initialDistance = 150;
        this.baselineDistance = 150; // CONSTANTE: referencia para calcular zoom real
        // Constant focal length for perspective (tuned on resize)
        this.focalLength = 800;
        
        this.initCanvas();
        this.setupInteraction();
    }
    
    initCanvas() {
        // Clear container and create canvas
        this.container.innerHTML = '';
        this.container.style.position = 'relative';
        
        // Create canvas element for rendering
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.container.clientWidth;
        this.canvas.height = this.container.clientHeight;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.display = 'block';
        this.canvas.style.cursor = 'grab';
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.zIndex = '1';
        
        this.container.appendChild(this.canvas);
        
    // Get 2D context with antialiasing
        this.ctx = this.canvas.getContext('2d', { alpha: false, willReadFrequently: false });
        
        // Create zoom controls UI
        this.createZoomControls();
        
        // Find the info panel (created in HTML) where we'll display node info
        this.infoPanelElement = document.getElementById('graph-info-panel');
        
        // Handle resizing
        window.addEventListener('resize', () => this.handleResize());
        // Calibrate focal length now that canvas size is known
        this.updateFocalByCanvas();
    }
    
    createZoomControls() {
        this.controlsDiv = document.createElement('div');
        this.controlsDiv.className = 'graph-zoom-controls';
        this.controlsDiv.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 10000;
            pointer-events: auto;
        `;
        
        const buttonStyle = `
            width: 40px;
            height: 40px;
            border: none;
            border-radius: 8px;
            background: rgba(30, 30, 50, 0.9);
            color: white;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.2s;
            backdrop-filter: blur(10px);
        `;
        
        // Zoom In button
        const zoomInBtn = document.createElement('button');
        zoomInBtn.innerHTML = '➕';
        zoomInBtn.style.cssText = buttonStyle;
        zoomInBtn.title = 'Acercar (Zoom In)';
        zoomInBtn.onmouseover = () => zoomInBtn.style.background = 'rgba(60, 120, 255, 0.9)';
        zoomInBtn.onmouseout = () => zoomInBtn.style.background = 'rgba(30, 30, 50, 0.9)';
        zoomInBtn.onclick = () => this.zoomIn();
        
        // Zoom Out button
        const zoomOutBtn = document.createElement('button');
        zoomOutBtn.innerHTML = '➖';
        zoomOutBtn.style.cssText = buttonStyle;
        zoomOutBtn.title = 'Alejar (Zoom Out)';
        zoomOutBtn.onmouseover = () => zoomOutBtn.style.background = 'rgba(60, 120, 255, 0.9)';
        zoomOutBtn.onmouseout = () => zoomOutBtn.style.background = 'rgba(30, 30, 50, 0.9)';
        zoomOutBtn.onclick = () => this.zoomOut();
        
        // Reset button
        const resetBtn = document.createElement('button');
        resetBtn.innerHTML = '🔄';
        resetBtn.style.cssText = buttonStyle;
        resetBtn.title = 'Resetear Vista';
        resetBtn.onmouseover = () => resetBtn.style.background = 'rgba(60, 120, 255, 0.9)';
        resetBtn.onmouseout = () => resetBtn.style.background = 'rgba(30, 30, 50, 0.9)';
        resetBtn.onclick = () => this.resetView();
        
        this.controlsDiv.appendChild(zoomInBtn);
        this.controlsDiv.appendChild(zoomOutBtn);
        this.controlsDiv.appendChild(resetBtn);
        
        this.container.appendChild(this.controlsDiv);
    }
    
    zoomIn() {
        this.camera.distance *= 0.85;
        this.camera.distance = Math.max(10, this.camera.distance);
        this.render();
    }
    
    zoomOut() {
        this.camera.distance *= 1.18;
        this.camera.distance = Math.min(2000, this.camera.distance);
        this.render();
    }
    
    setupInteraction() {
        // Mouse controls for rotation
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.canvas.style.cursor = 'grabbing';
            this.lastMouse = { x: e.clientX, y: e.clientY };
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            if (this.isDragging) {
                const dx = e.clientX - this.lastMouse.x;
                const dy = e.clientY - this.lastMouse.y;
                
                this.camera.rotation.y += dx * 0.01;
                this.camera.rotation.x += dy * 0.01;
                
                this.lastMouse = { x: e.clientX, y: e.clientY };
                this.render();
            } else {
                // Check for hover over nodes (visual only, no panel update)
                this.checkNodeHover(mouseX, mouseY);
            }
        });
        
        // Click to select a node
        this.canvas.addEventListener('click', (e) => {
            // Ignore clicks while dragging
            if (this.isDragging) return;
            
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            this.selectNodeByClick(mouseX, mouseY);
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            this.canvas.style.cursor = 'grab';
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.canvas.style.cursor = 'grab';
            // Reset hover visual (but keep selected panel if exists)
            this.hoveredNode = null;
            this.render();
        });
        
        // Mouse wheel for zoom - ensure preventDefault is respected
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 1.15 : 0.87;
            this.camera.distance *= delta;
            this.camera.distance = Math.max(10, Math.min(2000, this.camera.distance));
            this.render();
        }, { passive: false });
        
        // Double-click to reset view and clear selection
        this.canvas.addEventListener('dblclick', () => {
            this.resetView();
        });
    }
    
    checkNodeHover(mouseX, mouseY) {
        if (!this.graphData || !this.projectedNodes) {
            this.hoveredNode = null;
            this.render();
            return;
        }
        
        let foundNode = null;
        let foundIndex = -1;
        let minDistance = Infinity;
        
        // Check each node for hover - find the closest one within range
        for (let i = 0; i < this.projectedNodes.length; i++) {
            const p = this.projectedNodes[i];
            if (!p) continue;
            
            const baseSizeScale = p.scale / this.camera.zoom * 0.015;
            const size = Math.max(5, 10 * baseSizeScale);
            
            const dx = mouseX - p.x;
            const dy = mouseY - p.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            // Aumentar el área de detección
            const hitRadius = size + 15;
            
            if (distance <= hitRadius && distance < minDistance) {
                foundIndex = i;
                minDistance = distance;
            }
        }
        
        // Update hovered node (visual feedback only)
        if (foundIndex >= 0 && foundIndex !== this.hoveredNode) {
            this.hoveredNode = foundIndex;
            this.render();
        } else if (foundIndex === -1 && this.hoveredNode !== null) {
            this.hoveredNode = null;
            this.render();
        }
    }

    /**
     * Detecta si se hace click sobre un nodo y lo selecciona.
     * Actualiza el panel de información con sus conexiones.
     */
    selectNodeByClick(mouseX, mouseY) {
        if (!this.graphData || !this.projectedNodes) {
            return;
        }
        
        let foundIndex = -1;
        let minDistance = Infinity;
        
        // Check each node for click
        for (let i = 0; i < this.projectedNodes.length; i++) {
            const p = this.projectedNodes[i];
            if (!p) continue;
            
            const baseSizeScale = p.scale / this.camera.zoom * 0.015;
            const size = Math.max(5, 10 * baseSizeScale);
            
            const dx = mouseX - p.x;
            const dy = mouseY - p.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            const hitRadius = size + 15;
            
            if (distance <= hitRadius && distance < minDistance) {
                foundIndex = i;
                minDistance = distance;
            }
        }
        
        // Si encontramos un nodo, lo seleccionamos y actualizamos el panel
        if (foundIndex >= 0) {
            this.selectedNode = foundIndex;
            const node = this.graphData.nodes[foundIndex];
            this.updateInfoPanel(node, foundIndex);
            this.render();
        }
    }

    /**
     * Actualiza el panel de información blanco abajo del gráfico.
     * Se llama solo cuando se hace CLICK en un nodo.
     */
    updateInfoPanel(node, index) {
        if (!this.infoPanelElement) return;
        
        // Obtener conexiones del nodo
        const connections = this.adj && this.adj.get(index) ? Array.from(this.adj.get(index)) : [];
        const connectionLabels = connections.map(i => {
            const connectedNode = this.graphData.nodes[i];
            return connectedNode ? (connectedNode.label || `Nodo ${i}`) : `Nodo ${i}`;
        });

        const coords = `x: ${node.x.toFixed(2)} | y: ${node.y.toFixed(2)} | z: ${node.z.toFixed(2)}`;

        let html = `
            <div style="margin-bottom: 12px;">
                <div style="font-weight: 700; font-size: 14px; color: #000; margin-bottom: 6px;">
                    📍 ${node.label || 'Sin nombre'}
                </div>
                <div style="font-size: 12px; color: #555; margin-bottom: 10px;">
                    ${coords}
                </div>
            </div>
        `;

        if (connections.length > 0) {
            html += `
                <div>
                    <div style="font-weight: 700; font-size: 12px; color: #000; margin-bottom: 8px;">
                        🔗 Conexiones (${connections.length}):
                    </div>
                    <div style="
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                        gap: 8px;
                        max-height: 200px;
                        overflow-y: auto;
                        padding-right: 8px;
                    ">
                        ${connectionLabels.map((label, idx) => `
                            <div style="
                                background: #fff0e6;
                                border-left: 3px solid #FF6600;
                                padding: 6px 8px;
                                border-radius: 4px;
                                font-size: 11px;
                                color: #333;
                                word-break: break-word;
                            ">
                                ${label}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        } else {
            html += `
                <div style="font-size: 12px; color: #999; font-style: italic;">
                    Este nodo no tiene conexiones.
                </div>
            `;
        }

        this.infoPanelElement.innerHTML = html;
    }
    
    /**
     * Reset camera to initial view
     */
    resetView() {
        this.camera.rotation = { x: 0.2, y: 0.2 };
        this.camera.distance = this.initialDistance;
        this.camera.zoom = this.initialZoom;
        // Reset the info panel and selection
        this.selectedNode = null;
        this.hoveredNode = null;
        if (this.infoPanelElement) {
            this.infoPanelElement.innerHTML = '<div style="color: #666; font-size: 13px; text-align: center;">Pasa el cursor sobre un nodo para ver sus conexiones</div>';
        }
        this.render();
    }
    
    handleResize() {
        this.canvas.width = this.container.clientWidth;
        this.canvas.height = this.container.clientHeight;
        this.updateFocalByCanvas();
        if (this.graphData) {
            this.render();
        }
    }
    
    updateFocalByCanvas() {
        // Keep focal length sensible relative to viewport
        this.focalLength = Math.max(300, Math.min(this.canvas.width, this.canvas.height) * 0.9);
    }
    
    /**
     * Load and render graph data
     * @param {Object} data - Graph data with nodes and edges
     * @param {Array} data.nodes - Array of {x, y, z, label}
     * @param {Array} data.edges - Array of [nodeIndex1, nodeIndex2]
     * @param {Object} data.graphMetadata - Metadata including bbox
     */
    loadGraph(data) {
        this.graphData = data;
        // Build simple adjacency list to highlight neighbour edges/nodes on hover
        if (data && Array.isArray(data.edges)) {
            this.adj = new Map();
            for (const [a, b] of data.edges) {
                if (!this.adj.has(a)) this.adj.set(a, new Set());
                if (!this.adj.has(b)) this.adj.set(b, new Set());
                this.adj.get(a).add(b);
                this.adj.get(b).add(a);
            }
        } else {
            this.adj = new Map();
        }
        
        // Set camera to center of bounding box
        if (data.graphMetadata && data.graphMetadata.bbox) {
            const center = data.graphMetadata.bbox.center;
            this.camera.target = { x: center[0], y: center[1], z: center[2] };
            
            // Calculate initial distance based on bbox size for optimal view
            const bbox = data.graphMetadata.bbox;
            const size = Math.max(
                bbox.max[0] - bbox.min[0],
                bbox.max[1] - bbox.min[1],
                bbox.max[2] - bbox.min[2]
            );
            
            // Initial distance: CLOSER to see all connections clearly
            this.camera.distance = size * 1.8; // Reduced from 2.5 to 1.8
            this.initialDistance = this.camera.distance;
            this.camera.zoom = Math.min(this.canvas.width, this.canvas.height) / (size * 1.5);
            this.initialZoom = this.camera.zoom;
            // Update focal length relative to viewport for sensible scaling
            this.focalLength = Math.min(this.canvas.width, this.canvas.height) * 0.9;
        }
        
        // Reset rotation for better initial view
        this.camera.rotation = { x: 0.2, y: 0.2 };
        
        this.render();
    }
    
    /**
     * Project 3D point to 2D screen coordinates
     */
    project3D(x, y, z) {
    // Simple perspective projection using constant focal length
        const cx = this.camera.target.x;
        const cy = this.camera.target.y;
        const cz = this.camera.target.z;
        
        // Translate to camera space
        let px = x - cx;
        let py = y - cy;
        let pz = z - cz;
        
        // Apply rotation
        const cosX = Math.cos(this.camera.rotation.x);
        const sinX = Math.sin(this.camera.rotation.x);
        const cosY = Math.cos(this.camera.rotation.y);
        const sinY = Math.sin(this.camera.rotation.y);
        
        // Rotate around Y axis
        let tx = px * cosY - pz * sinY;
        let tz = px * sinY + pz * cosY;
        px = tx;
        pz = tz;
        
        // Rotate around X axis
        let ty = py * cosX - pz * sinX;
        tz = py * sinX + pz * cosX;
        py = ty;
        pz = tz;
        
    // Perspective projection with improved depth
    // Keep focal length constant; decreasing distance increases scale properly
    const denom = Math.max(1e-3, (this.camera.distance + pz));
    const scale = this.camera.zoom * this.focalLength / denom;
        
        const screenX = this.canvas.width / 2 + px * scale;
        const screenY = this.canvas.height / 2 - py * scale;
        
        return { x: screenX, y: screenY, z: pz, scale };
    }
    
    /**
     * Render the graph
     */
    render() {
        if (!this.graphData || !this.ctx) return;
        
        const ctx = this.ctx;
        const { nodes, edges } = this.graphData;
        
        // Clear canvas
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Fondo estilo científico moderno (similar a Plotly oscuro)
        const gradient = ctx.createRadialGradient(
            this.canvas.width / 2, this.canvas.height / 2, 0,
            this.canvas.width / 2, this.canvas.height / 2, this.canvas.width / 1.5
        );
        gradient.addColorStop(0, '#1e1e2e');
        gradient.addColorStop(0.5, '#181825');
        gradient.addColorStop(1, '#0f0f1a');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Optional: Add subtle grid pattern for depth
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
        ctx.lineWidth = 1;
        for (let i = 0; i < this.canvas.width; i += 50) {
            ctx.beginPath();
            ctx.moveTo(i, 0);
            ctx.lineTo(i, this.canvas.height);
            ctx.stroke();
        }
        for (let i = 0; i < this.canvas.height; i += 50) {
            ctx.beginPath();
            ctx.moveTo(0, i);
            ctx.lineTo(this.canvas.width, i);
            ctx.stroke();
        }
        
        // Project all nodes to 2D and store for hover detection
        this.projectedNodes = nodes.map(node => {
            const p = this.project3D(node.x, node.y, node.z);
            return { ...p, label: node.label, color: this.nodeColor(node) };
        });
        
        // Sort by depth (z) for proper rendering order
        const sortedIndices = this.projectedNodes.map((p, i) => ({ z: p.z, i }))
            .sort((a, b) => a.z - b.z)
            .map(item => item.i);
        
        // Draw ALL edges - MÁXIMA VISIBILIDAD
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        
        // Sort edges by average depth for better rendering
        const edgesWithDepth = edges.map(([i, j]) => {
            const p1 = this.projectedNodes[i];
            const p2 = this.projectedNodes[j];
            if (!p1 || !p2) return null;
            const avgZ = (p1.z + p2.z) / 2;
            return { i, j, p1, p2, avgZ };
        }).filter(e => e !== null);
        
        edgesWithDepth.sort((a, b) => a.avgZ - b.avgZ);
        
        // Draw ALL edges with highlighting for selected/hovered nodes
        for (const edge of edgesWithDepth) {
            const { p1, p2, avgZ } = edge;
            
            // Depth factor for subtle 3D effect
            const depthFactor = Math.max(0.3, Math.min(1, (avgZ + 150) / 300));
            
            // Detectar si esta arista está conectada al nodo seleccionado o hovado
            const isSelectedEdge = this.selectedNode !== null && (edge.i === this.selectedNode || edge.j === this.selectedNode);
            const isHoveredEdge = this.hoveredNode !== null && (edge.i === this.hoveredNode || edge.j === this.hoveredNode);
            
            let lineWidth, opacity, color;
            
            if (isSelectedEdge) {
                // Rojo/magenta para aristas del nodo seleccionado (MÁS VISIBLE)
                lineWidth = 4.0 + (depthFactor * 0.8);
                opacity = 0.95;
                color = `rgba(255, 100, 150, ${opacity})`;
            } else if (isHoveredEdge) {
                // Amarillo/naranja para aristas del nodo hovado
                lineWidth = 3.0 + (depthFactor * 0.8);
                opacity = 0.9;
                color = `rgba(255, 220, 100, ${opacity})`;
            } else {
                // Cyan/azul por defecto
                lineWidth = 2.0 + (depthFactor * 0.8);
                opacity = 0.5 + depthFactor * 0.3;
                color = `rgba(99, 179, 237, ${opacity})`;
            }
            
            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
        }
        
        // Draw nodes - SIMILAR A PLOTLY CON HOVER + SELECTION HIGHLIGHT
        for (const idx of sortedIndices) {
            const p = this.projectedNodes[idx];
            if (!p) continue;
            
            // Node size varies with depth
            const baseSizeScale = p.scale / this.camera.zoom * 0.015;
            const size = Math.max(4, 9 * baseSizeScale);
            
            const isSelected = (this.selectedNode === idx);
            const isHovered = (this.hoveredNode === idx);
            const isNeighborOfSelected = this.selectedNode !== null && this.adj && this.adj.get(this.selectedNode) && this.adj.get(this.selectedNode).has(idx);
            const isNeighborOfHovered = this.hoveredNode !== null && this.adj && this.adj.get(this.hoveredNode) && this.adj.get(this.hoveredNode).has(idx);
            
            const selectedScale = isSelected ? 1.6 : 1.0;
            const hoverScale = isHovered ? 1.4 : 1.0;
            const neighbourScale = (isNeighborOfSelected || isNeighborOfHovered) ? 1.2 : 1.0;
            const finalSize = size * selectedScale * hoverScale * neighbourScale;
            
            // Depth factor for color
            const depthFactor = Math.max(0.3, Math.min(1, (p.z + 150) / 300));
            
            // Create radial gradient for 3D sphere effect
            const gradient = ctx.createRadialGradient(
                p.x - finalSize * 0.3, p.y - finalSize * 0.3, 0,
                p.x, p.y, finalSize
            );
            
            if (isSelected) {
                // Selected node - rojo/magenta brillante (CLICK)
                gradient.addColorStop(0, 'rgba(255, 100, 150, 1)');
                gradient.addColorStop(0.6, 'rgba(255, 80, 120, 0.95)');
                gradient.addColorStop(1, 'rgba(220, 50, 100, 0.8)');
            } else if (isHovered) {
                // Hovered node - amarillo/naranja brillante (MOUSE)
                gradient.addColorStop(0, 'rgba(255, 220, 100, 1)');
                gradient.addColorStop(0.6, 'rgba(255, 180, 50, 0.95)');
                gradient.addColorStop(1, 'rgba(230, 140, 30, 0.8)');
            } else {
                // Color por clasificación (átomo/residuo)
                const base = this.projectedNodes[idx].color;
                const [r, g, b] = base;
                gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.95)`);
                gradient.addColorStop(0.7, `rgba(${Math.max(0,r-30)}, ${Math.max(0,g-20)}, ${Math.max(0,b-30)}, 0.9)`);
                gradient.addColorStop(1, `rgba(${Math.max(0,r-60)}, ${Math.max(0,g-40)}, ${Math.max(0,b-60)}, 0.75)`);
            }
            
            // Draw node
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(p.x, p.y, finalSize, 0, Math.PI * 2);
            ctx.fill();
            
            // Border - grueso si está seleccionado o hovado
            let borderWidth = 1.5;
            let borderColor = `rgba(255, 255, 255, ${0.5 + depthFactor * 0.3})`;
            
            if (isSelected) {
                borderWidth = 3.5;
                borderColor = 'rgba(255, 255, 255, 1)';
            } else if (isHovered) {
                borderWidth = 3.0;
                borderColor = 'rgba(255, 255, 255, 1)';
            } else if (isNeighborOfSelected || isNeighborOfHovered) {
                borderWidth = 2.0;
                borderColor = 'rgba(255, 220, 100, 0.9)';
            }
            
            ctx.strokeStyle = borderColor;
            ctx.lineWidth = borderWidth;
            ctx.stroke();

            
            // Inner glow sutil
            if (!isHovered) {
                ctx.strokeStyle = `rgba(255, 200, 255, ${0.3 + depthFactor * 0.2})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, finalSize * 0.5, 0, Math.PI * 2);
                ctx.stroke();
            }
        }
        
        // Draw info panel - LIMPIO Y PROFESIONAL
        const padding = 14;
        const lineHeight = 22;
        const panelWidth = 240;
        const panelHeight = 70;
        
        // Semi-transparent dark panel
        ctx.fillStyle = 'rgba(20, 20, 40, 0.85)';
        ctx.fillRect(10, 10, panelWidth, panelHeight);
        
        // Border
        ctx.strokeStyle = 'rgba(99, 179, 237, 0.4)';
        ctx.lineWidth = 1;
        ctx.strokeRect(10, 10, panelWidth, panelHeight);
        
        // Info text
        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.font = 'bold 15px "Segoe UI", Arial, sans-serif';
        ctx.fillText(`📊 Nodos: ${nodes.length} | Aristas: ${edges.length}`, padding + 6, padding + lineHeight);
        
        ctx.font = '13px "Segoe UI", Arial, sans-serif';
        // Calcular zoom de manera inversamente proporcional a la distancia
        // Usar baselineDistance como referencia CONSTANTE
        const zoomPercent = Math.round((this.baselineDistance / this.camera.distance) * 100);
        const displayZoom = Math.max(10, Math.min(1000, zoomPercent));
        ctx.fillText(`🔍 Zoom: ${displayZoom}%`, padding + 6, padding + lineHeight * 2);
        
        ctx.fillStyle = 'rgba(180, 220, 255, 0.85)';
        ctx.font = '12px "Segoe UI", Arial, sans-serif';
        ctx.fillText('🖱️ Arrastrar para rotar | Hover en nodo para info', padding + 6, padding + lineHeight * 3);
    }
    
    /**
     * Clear the graph
     */
    clear() {
        this.graphData = null;
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }
    
    /**
     * Destroy the renderer and clean up
     */
    destroy() {
        window.removeEventListener('resize', this.handleResize);
        
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        
        this.canvas = null;
        this.ctx = null;
        this.graphData = null;
        this.projectedNodes = null;
        this.infoPanelElement = null;
        this.adj = null;
    }

    // === Utility: color mapping based on atom/residue classification ===
    nodeColor(node) {
        const type = node.element || node.type || null;
        const label = node.label || '';
        // Intenta extraer el nombre de residuo del label tipo "A:HIS:28:CA"
        let residue = null;
        const parts = typeof label === 'string' ? label.split(':') : [];
        if (parts.length >= 2) residue = parts[1];
        const atomName = parts.length >= 4 ? parts[3] : null;

        // Paleta CPK mínima por elemento
        const cpk = {
            H: [255, 255, 255],
            C: [80, 80, 80],
            N: [48, 80, 248],
            O: [255, 13, 13],
            S: [255, 200, 50],
            P: [255, 165, 0]
        };
        if (type && cpk[type]) return cpk[type];

        // Colores por residuo (HIS amarillo como se solicitó)
        const residueMap = {
            HIS: [255, 220, 100],
            PHE: [180, 120, 200],
            TYR: [200, 160, 60],
            TRP: [120, 60, 200],
            LYS: [0, 102, 255],
            ARG: [0, 150, 255],
            ASP: [255, 80, 80],
            GLU: [255, 100, 100],
            SER: [220, 220, 255],
            THR: [200, 220, 255],
            GLY: [220, 220, 220],
            ALA: [200, 200, 200],
            CYS: [255, 230, 120],
            MET: [255, 200, 80],
            PRO: [170, 170, 170],
            ASN: [120, 200, 255],
            GLN: [120, 200, 255],
            ILE: [200, 200, 0],
            LEU: [200, 200, 0],
            VAL: [200, 200, 0]
        };
        if (residue && residueMap[residue]) return residueMap[residue];

        // Diferenciar CA en vista de residuos
        if (atomName === 'CA') return [255, 105, 180];

        // Fallback agradable púrpura
        return [210, 120, 210];
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.MolstarGraphRenderer = MolstarGraphRenderer;
}
