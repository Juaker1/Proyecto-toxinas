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
        this.visibility = { nodes: true, edges: true };
        this.defaultCameraState = null;
        // Node state: selectedNode (CLICK), hoveredNode (MOUSE OVER)
        this.selectedNode = null; // nodo seleccionado con CLICK (muestra conexiones en panel)
        this.hoveredNode = null; // nodo bajo el cursor (solo resalta colores)
        this.camera = {
            rotation: { x: 0.3, y: 0.3 },
            zoom: 1,
            distance: 150,
            target: { x: 0, y: 0, z: 0 }
        };
        this.segmentHighlight = null;
        this.segmentNeighborHighlight = null;
        this.activeSegmentId = null;
        this.isDragging = false;
        this.isRotating = false;
        this.isPanning = false;
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
        
        // Forzar dimensiones mínimas si el contenedor no tiene tamaño
        let containerWidth = this.container.clientWidth;
        let containerHeight = this.container.clientHeight;
        
        // Si las dimensiones son 0, usar valores por defecto y forzar al contenedor
        if (containerWidth === 0 || containerHeight === 0) {
            console.warn('Graph container has zero dimensions, applying defaults');
            containerWidth = 800;
            containerHeight = 600;
            this.container.style.minWidth = '800px';
            this.container.style.minHeight = '600px';
        }
        
        this.canvas.width = containerWidth;
        this.canvas.height = containerHeight;
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
        
        if (!this.ctx) {
            console.error('Failed to get 2D context for canvas');
            return;
        }
        
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
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        this.canvas.addEventListener('mousedown', (e) => {
            if (e.button === 0) {
                this.isRotating = true;
                this.canvas.style.cursor = 'grabbing';
            } else if (e.button === 2) {
                this.isPanning = true;
                this.canvas.style.cursor = 'move';
            } else {
                return;
            }
            this.isDragging = true;
            this.lastMouse = { x: e.clientX, y: e.clientY };
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            if (this.isRotating || this.isPanning) {
                const dx = e.clientX - this.lastMouse.x;
                const dy = e.clientY - this.lastMouse.y;
                
                if (this.isRotating) {
                    this.camera.rotation.y += dx * 0.01;
                    this.camera.rotation.x += dy * 0.01;
                    this.render();
                }

                if (this.isPanning) {
                    this.panCamera(dx, dy);
                }
                
                this.lastMouse = { x: e.clientX, y: e.clientY };
            } else {
                // Check for hover over nodes (visual only, no panel update)
                if (this.graphData && this.projectedNodes) {
                    this.checkNodeHover(mouseX, mouseY);
                }
            }
        });
        
        // Click to select a node
        this.canvas.addEventListener('click', (e) => {
            // Ignore clicks while dragging
            if (this.isDragging || this.isRotating || this.isPanning) return;
            
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            this.selectNodeByClick(mouseX, mouseY);
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            this.isRotating = false;
            this.isPanning = false;
            this.canvas.style.cursor = 'grab';
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.isRotating = false;
            this.isPanning = false;
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
     * Actualiza el panel de información con el nuevo diseño Card Grid.
     * Se llama cuando se hace CLICK en un nodo del grafo.
     */
    updateInfoPanel(node, index) {
        // Ocultar estado vacío y mostrar detalles
        const emptyState = document.querySelector('.graph-info-empty');
        const detailsDiv = document.getElementById('graph-info-details');
        
        if (emptyState) emptyState.style.display = 'none';
        if (detailsDiv) detailsDiv.style.display = 'flex';
        
        // Actualizar información básica del nodo
        const nodeNameEl = document.getElementById('node-name');
        const nodeTypeEl = document.getElementById('node-type');
        
        if (nodeNameEl) nodeNameEl.textContent = node.label || 'Nodo';
        if (nodeTypeEl) nodeTypeEl.textContent = 'Residuo';
        
        // Actualizar métricas (si están disponibles en el nodo)
        this.updateNodeMetrics(node);
        
        // Actualizar conexiones con el nuevo diseño
        this.updateConnectionsGrid(node, index);
        
        // Actualizar conexiones en el modal si está abierto
        const modalOverlay = document.getElementById('graph-controls-modal-overlay');
        if (modalOverlay && modalOverlay.classList.contains('open')) {
            this.updateModalConnectionsGrid(node, index);
        }
    }
    
    /**
     * Actualiza las métricas del nodo seleccionado
     */
    updateNodeMetrics(node) {
        const degreeEl = document.getElementById('node-degree');
        const betweennessEl = document.getElementById('node-betweenness');
        const closenessEl = document.getElementById('node-closeness');
        
        if (degreeEl) degreeEl.textContent = (node.degree || 0).toFixed(3);
        if (betweennessEl) betweennessEl.textContent = (node.betweenness || 0).toFixed(3);
        if (closenessEl) closenessEl.textContent = (node.closeness || 0).toFixed(3);
    }
    
    /**
     * Genera el grid de conexiones con el nuevo diseño tipo card
     */
    updateConnectionsGrid(node, index) {
        const connectionsGrid = document.getElementById('node-connected');
        const connectionsBadge = document.getElementById('connections-badge');
        
        if (!connectionsGrid) return;
        
        // Obtener conexiones del nodo
        let connections = this.adj && this.adj.get(index) ? Array.from(this.adj.get(index)) : [];
        // Si el nodo marcado globalmente está en las conexiones, muévelo al inicio
        const globalSel = (this.selectedNode !== null) ? this.selectedNode : -1;
        if (globalSel >= 0) {
            const pos = connections.indexOf(globalSel);
            if (pos >= 0) {
                connections.splice(pos, 1);
                connections.unshift(globalSel);
            }
        }
        
        // Actualizar badge con el número de conexiones
        if (connectionsBadge) {
            connectionsBadge.textContent = connections.length;
        }
        
        // Limpiar grid
        connectionsGrid.innerHTML = '';
        
        // Si no hay conexiones, mostrar estado vacío
        if (connections.length === 0) {
            connectionsGrid.innerHTML = `
                <div class="connections-empty">
                    <i class="fas fa-unlink"></i>
                    <span>Este nodo no tiene conexiones</span>
                </div>
            `;
            return;
        }
        
        // Generar cards para cada conexión
        connections.forEach(connIndex => {
            const connectedNode = this.graphData.nodes[connIndex];
            if (!connectedNode) return;
            
            const card = document.createElement('div');
            card.className = 'connection-card';
            
            // Calcular distancia si está disponible
            const distance = this.calculateDistance(node, connectedNode);
            const distanceStr = distance ? `${distance.toFixed(1)}Å` : '';
            
            card.innerHTML = `
                <div class="connection-card-icon">
                    <i class="fas fa-link"></i>
                </div>
                <div class="connection-card-name">${connectedNode.label || `Nodo ${connIndex}`}</div>
                ${distanceStr ? `<div class="connection-card-distance">${distanceStr}</div>` : ''}
            `;
            
            // Event listener para hacer click en una conexión
            card.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectNodeByIndex(connIndex);
            });

            // Si la conexión es el nodo seleccionado actualmente, resaltar
            if (this.selectedNode !== null && connIndex === this.selectedNode) {
                card.classList.add('active');
                card.setAttribute('aria-current', 'true');
            } else {
                card.removeAttribute('aria-current');
            }

            // (duplicate highlight removed; handled above with aria-current)
            
            connectionsGrid.appendChild(card);
        });
    }
    
    /**
     * Actualiza el panel de conexiones en el modal
     */
    updateModalConnectionsGrid(node, index) {
        const modalConnectionsGrid = document.getElementById('modal-node-connected');
        const modalConnectionsBadge = document.getElementById('modal-connections-badge');
        const modalCurrentNodeName = document.getElementById('modal-current-node-name');
        const modalPrevBtn = document.getElementById('modal-connections-prev');
        const modalNextBtn = document.getElementById('modal-connections-next');
        const modalIndicators = document.getElementById('modal-carousel-indicators');
        
        if (!modalConnectionsGrid) return;
        
        // Mostrar el nombre del nodo actual
        if (modalCurrentNodeName) {
            modalCurrentNodeName.textContent = node.label || `Nodo ${index}`;
        }
        
        // Obtener conexiones del nodo (guardamos original para contar)
        const originalConnections = this.adj && this.adj.get(index) ? Array.from(this.adj.get(index)) : [];
        let connections = originalConnections.slice();
        // Insertar el nodo actualmente seleccionado al principio del track si hace falta
        const globalSel = (this.selectedNode !== null) ? this.selectedNode : -1;
        let injectedSelectedNotLinked = false;
        if (globalSel >= 0) {
            const pos = connections.indexOf(globalSel);
            if (pos >= 0) {
                connections.splice(pos, 1);
                connections.unshift(globalSel);
            } else {
                connections.unshift(globalSel); // mantener visible la selección
                injectedSelectedNotLinked = true;
            }
        }
        
        // Actualizar badge con el número de conexiones (no contamos el seleccionado insertado manualmente)
        if (modalConnectionsBadge) {
            modalConnectionsBadge.textContent = originalConnections.length;
        }
        
        // Limpiar grid
        modalConnectionsGrid.innerHTML = '';
        
        // Si no hay conexiones, mostrar estado vacío
        if (connections.length === 0) {
            modalConnectionsGrid.innerHTML = `
                <div style="flex: 1; text-align: center; color: #9ca3af; padding: 20px;">
                    <i class="fas fa-unlink" style="font-size: 24px; margin-bottom: 8px;"></i>
                    <span>Este nodo no tiene conexiones</span>
                </div>
            `;
            // Ocultar controles de navegación
            if (modalPrevBtn) modalPrevBtn.style.display = 'none';
            if (modalNextBtn) modalNextBtn.style.display = 'none';
            if (modalIndicators) modalIndicators.innerHTML = '';
            return;
        }
        
        // Configuración inicial del carrusel
        let cardsPerPage = 4; // se recalculará en base al ancho del contenedor
        let totalPages = Math.ceil(connections.length / cardsPerPage);
        let currentPage = 0;
        
        // Generar todas las cards
        connections.forEach(connIndex => {
            const connectedNode = this.graphData.nodes[connIndex];
            if (!connectedNode) return;
            
            const card = document.createElement('div');
            card.className = 'modal-connection-card';
            
            // Calcular distancia si está disponible
            const distance = this.calculateDistance(node, connectedNode);
            const distanceStr = distance ? `${distance.toFixed(1)}Å` : '';
            
            // Render icon + small name label under it
            card.innerHTML = `
                <div class="modal-connection-card-icon">
                    <i class="fas fa-link"></i>
                </div>
                <div class="modal-connection-card-name">${connectedNode.label || `Nodo ${connIndex}`}</div>
            `;
            card.title = connectedNode.label || `Nodo ${connIndex}`;
            card.setAttribute('role', 'button');
            card.setAttribute('aria-label', connectedNode.label || `Nodo ${connIndex}`);
            card.tabIndex = 0;
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.selectNodeByIndex(connIndex);
                }
            });
            
            // Event listener para hacer click en una conexión
            card.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectNodeByIndex(connIndex);
            });

            // Si hemos inyectado el seleccionado en la lista pero no es originalmente una conexión, marcarlo
            if (injectedSelectedNotLinked && connIndex === globalSel) {
                card.dataset.selectedNotLinked = 'true';
                card.title = (card.title || '') + ' (Seleccionado)';
            }
            
            modalConnectionsGrid.appendChild(card);
        });
        
        // Función para actualizar la posición del carrusel
        const updateCarousel = () => {
            // Medir dimensiones reales
            const carouselViewport = modalConnectionsGrid.parentElement;
            const containerWidth = carouselViewport ? carouselViewport.clientWidth : 820;
            const firstCard = modalConnectionsGrid.firstElementChild;
            const cardWidth = firstCard ? firstCard.getBoundingClientRect().width : 120;
            const gap = 8; // debe coincidir con el CSS
            // recalcular cuantas cards caben por página
            cardsPerPage = Math.max(1, Math.floor(containerWidth / (cardWidth + gap)));
            const pageWidth = cardsPerPage * (cardWidth + gap) - gap;
            // recalcular totalPages si cambió
            totalPages = Math.max(1, Math.ceil(connections.length / cardsPerPage));
            // Asegurar currentPage dentro de los límites
            currentPage = Math.min(currentPage, Math.max(0, totalPages - 1));
            const leftPadding = Math.max(0, (containerWidth - pageWidth) / 2);
            const translateX = leftPadding - currentPage * pageWidth;
            modalConnectionsGrid.style.transform = `translateX(${translateX}px)`;
            
            // Actualizar botones
            if (modalPrevBtn) {
                modalPrevBtn.style.display = (totalPages > 1 && currentPage > 0) ? 'flex' : 'none';
                modalPrevBtn.disabled = currentPage === 0;
            }
            if (modalNextBtn) {
                modalNextBtn.style.display = (totalPages > 1 && currentPage < totalPages - 1) ? 'flex' : 'none';
                modalNextBtn.disabled = currentPage === totalPages - 1;
            }
            
            // Actualizar indicadores
            if (modalIndicators) {
                modalIndicators.innerHTML = '';
                for (let i = 0; i < totalPages; i++) {
                    const indicator = document.createElement('div');
                    indicator.className = `modal-carousel-indicator ${i === currentPage ? 'active' : ''}`;
                    indicator.addEventListener('click', () => {
                        currentPage = i;
                        updateCarousel();
                    });
                    modalIndicators.appendChild(indicator);
                }
            }
        };
        
        // Event listeners para navegación
        if (modalPrevBtn) {
            modalPrevBtn.onclick = () => {
                if (currentPage > 0) {
                    currentPage--;
                    updateCarousel();
                }
            };
        }
        
        if (modalNextBtn) {
            modalNextBtn.onclick = () => {
                if (currentPage < totalPages - 1) {
                    currentPage++;
                    updateCarousel();
                }
            };
        }
        
        // Si hay un nodo seleccionado que sea parte de las conexiones, mostrar su página
        const selectedConnIndex = (this.selectedNode !== null) ? connections.findIndex(c => c === this.selectedNode) : -1;
        if (selectedConnIndex >= 0) {
            currentPage = Math.floor(selectedConnIndex / cardsPerPage);
        }
        // Añadir listener de resize para recalcular el carousel (solo una vez por renderer)
        if (!this._modalCarouselResizeHandler) {
            this._modalCarouselResizeHandler = () => {
                try { updateCarousel(); } catch (e) {}
            };
            window.addEventListener('resize', this._modalCarouselResizeHandler);
        }
        // Inicializar carrusel
        updateCarousel();
    }
    
    /**
     * Calcula la distancia euclidiana entre dos nodos
     */
    calculateDistance(node1, node2) {
        if (!node1 || !node2) return null;
        const dx = node1.x - node2.x;
        const dy = node1.y - node2.y;
        const dz = node1.z - node2.z;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
    
    /**
     * Selecciona un nodo por su índice (usado al hacer click en una conexión)
     */
    selectNodeByIndex(index) {
        if (!this.graphData || !this.graphData.nodes[index]) return;
        
        this.selectedNode = index;
        const node = this.graphData.nodes[index];
        this.updateInfoPanel(node, index);
        this.render();
    }

    /**
     * Selecciona un nodo utilizando identificadores de residuo
     */
    selectNodeByResidue(chain, aa, pos, atom) {
        if (!this.graphData || !Array.isArray(this.graphData.nodes)) {
            return false;
        }

        const normalize = (value) => (value || '').toString().trim().toUpperCase();
        const parseLabel = (label) => {
            const safeLabel = normalize(label);
            const parts = safeLabel.split(':');
            return {
                chain: parts[0] || '',
                aa: parts[1] || '',
                pos: parts[2] || '',
                atom: parts[3] || ''
            };
        };

        const target = {
            chain: normalize(chain),
            aa: normalize(aa),
            pos: normalize(pos),
            atom: normalize(atom)
        };

        if (!target.chain || !target.aa || !target.pos) {
            return false;
        }

        const exactMatches = [];
        const atomPrefixMatches = [];
        const residueOnlyMatches = [];

        this.graphData.nodes.forEach((node, index) => {
            const parsed = parseLabel(node?.label || node?.id || node?.name || '');

            if (parsed.chain !== target.chain || parsed.aa !== target.aa || parsed.pos !== target.pos) {
                return;
            }

            if (target.atom) {
                if (parsed.atom === target.atom) {
                    exactMatches.push(index);
                    return;
                }

                if (parsed.atom && parsed.atom.startsWith(target.atom)) {
                    atomPrefixMatches.push(index);
                    return;
                }

                if (!parsed.atom) {
                    residueOnlyMatches.push(index);
                    return;
                }
            } else {
                if (!parsed.atom) {
                    exactMatches.push(index);
                } else {
                    atomPrefixMatches.push(index);
                }
            }
        });

        let foundIndex = -1;
        if (exactMatches.length > 0) {
            foundIndex = exactMatches[0];
        } else if (atomPrefixMatches.length > 0) {
            foundIndex = atomPrefixMatches[0];
        } else if (!target.atom && residueOnlyMatches.length > 0) {
            foundIndex = residueOnlyMatches[0];
        }

        if (foundIndex === -1 && target.atom) {
            // Como último recurso, si no existe el átomo solicitado pero sí el residuo, seleccionamos el primero
            if (residueOnlyMatches.length > 0) {
                foundIndex = residueOnlyMatches[0];
            }
        }

        if (foundIndex === -1) {
            return false;
        }

        const node = this.graphData.nodes[foundIndex];
        if (node && typeof node.x === 'number' && typeof node.y === 'number' && typeof node.z === 'number') {
            this.camera.target = { x: node.x, y: node.y, z: node.z };
        }

        this.selectNodeByIndex(foundIndex);
        return true;
    }

    highlightSegment(segmentId) {
        const normalized = segmentId?.toString().trim();
        if (!normalized || !this.graphData || !Array.isArray(this.graphData.nodes)) {
            this.clearSegmentHighlight();
            return { found: false, count: 0, neighborCount: 0 };
        }

        const nodes = [];
        this.graphData.nodes.forEach((node, index) => {
            const residueNumber = this.getResidueNumber(node);
            if (residueNumber !== null && normalized === residueNumber.toString().trim()) {
                nodes.push(index);
            }
        });

        if (!nodes.length) {
            this.clearSegmentHighlight();
            return { found: false, count: 0, neighborCount: 0 };
        }

        this.activeSegmentId = normalized;
        this.segmentHighlight = new Set(nodes);
        const neighbors = new Set();
        nodes.forEach((idx) => {
            const adjacency = this.adj?.get(idx);
            if (!adjacency) return;
            adjacency.forEach((neighborIdx) => {
                if (!this.segmentHighlight.has(neighborIdx)) {
                    neighbors.add(neighborIdx);
                }
            });
        });
        this.segmentNeighborHighlight = neighbors;
        this.focusOnNodes(nodes);
        this.render();
        return { found: true, count: nodes.length, neighborCount: neighbors.size };
    }

    clearSegmentHighlight() {
        if (!this.segmentHighlight && !this.segmentNeighborHighlight && !this.activeSegmentId) {
            return;
        }
        this.segmentHighlight = null;
        this.segmentNeighborHighlight = null;
        this.activeSegmentId = null;
        this.render();
    }

    getResidueNumber(node) {
        if (!node) return null;
        if (node.residueNumber !== undefined && node.residueNumber !== null) {
            return node.residueNumber;
        }
        if (node.residue_number !== undefined && node.residue_number !== null) {
            return node.residue_number;
        }
        const label = node.label || node.name || node.id;
        if (typeof label === 'string') {
            const parts = label.split(':');
            if (parts.length >= 3 && parts[2]) {
                return parts[2];
            }
        }
        return null;
    }

    focusOnNodes(indices) {
        if (!this.graphData || !Array.isArray(this.graphData.nodes) || !indices.length) {
            return;
        }
        const coords = indices
            .map((idx) => this.graphData.nodes[idx])
            .filter((node) => node && isFinite(node.x) && isFinite(node.y) && isFinite(node.z));
        if (!coords.length) {
            return;
        }
        const center = coords.reduce((acc, node) => {
            acc.x += node.x;
            acc.y += node.y;
            acc.z += node.z;
            return acc;
        }, { x: 0, y: 0, z: 0 });
        center.x /= coords.length;
        center.y /= coords.length;
        center.z /= coords.length;
        this.camera.target = center;
        let maxRadius = 0;
        coords.forEach((node) => {
            const dx = node.x - center.x;
            const dy = node.y - center.y;
            const dz = node.z - center.z;
            const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (dist > maxRadius) {
                maxRadius = dist;
            }
        });
        if (isFinite(maxRadius) && maxRadius > 0) {
            this.camera.distance = Math.max(30, maxRadius * 6);
        }
    }
    
    /**
     * Reset camera to initial view
     */
    resetView() {
        if (this.defaultCameraState) {
            this.camera.rotation = { ...this.defaultCameraState.rotation };
            this.camera.target = { ...this.defaultCameraState.target };
            this.camera.distance = this.defaultCameraState.distance;
            this.camera.zoom = this.defaultCameraState.zoom;
        } else {
            this.camera.rotation = { x: 0.2, y: 0.2 };
            this.camera.distance = this.initialDistance;
            this.camera.zoom = this.initialZoom;
        }
        // Reset the info panel and selection
        this.selectedNode = null;
        this.hoveredNode = null;
        if (this.infoPanelElement) {
            const emptyState = this.infoPanelElement.querySelector('.graph-info-empty');
            const detailsDiv = document.getElementById('graph-info-details');
            const connectionsGrid = document.getElementById('node-connected');
            const connectionsBadge = document.getElementById('connections-badge');
            const nodeNameEl = document.getElementById('node-name');
            const nodeTypeEl = document.getElementById('node-type');
            const degreeEl = document.getElementById('node-degree');
            const betweennessEl = document.getElementById('node-betweenness');
            const closenessEl = document.getElementById('node-closeness');

            if (emptyState) emptyState.style.display = 'flex';
            if (detailsDiv) detailsDiv.style.display = 'none';
            if (connectionsGrid) connectionsGrid.innerHTML = '';
            if (connectionsBadge) connectionsBadge.textContent = '0';
            if (nodeNameEl) nodeNameEl.textContent = '-';
            if (nodeTypeEl) nodeTypeEl.textContent = 'Residuo';
            if (degreeEl) degreeEl.textContent = '-';
            if (betweennessEl) betweennessEl.textContent = '-';
            if (closenessEl) closenessEl.textContent = '-';
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

        this.segmentHighlight = null;
        this.segmentNeighborHighlight = null;
        this.activeSegmentId = null;
        
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
            this.baselineDistance = this.camera.distance;
            this.camera.zoom = Math.min(this.canvas.width, this.canvas.height) / (size * 1.5);
            this.initialZoom = this.camera.zoom;
            // Update focal length relative to viewport for sensible scaling
            this.focalLength = Math.min(this.canvas.width, this.canvas.height) * 0.9;
        }
        
        // Reset rotation for better initial view
        this.camera.rotation = { x: 0.2, y: 0.2 };
        this.saveCameraDefaults();
        
        this.render();
    }

    saveCameraDefaults() {
        this.defaultCameraState = {
            target: { ...this.camera.target },
            rotation: { ...this.camera.rotation },
            distance: this.camera.distance,
            zoom: this.camera.zoom
        };
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

    panCamera(dx, dy) {
        const yaw = this.camera.rotation.y;
        const pitch = this.camera.rotation.x;
        const panFactor = Math.max(0.15, this.camera.distance / 600);
        const moveX = (-dx * Math.cos(yaw) + dy * Math.sin(pitch) * Math.sin(yaw)) * panFactor;
        const moveY = (dy * Math.cos(pitch)) * panFactor;
        const moveZ = (-dx * Math.sin(yaw) - dy * Math.sin(pitch) * Math.cos(yaw)) * panFactor;

        this.camera.target.x += moveX;
        this.camera.target.y += moveY;
        this.camera.target.z += moveZ;
        this.render();
    }
    
    /**
     * Render the graph
     */
    render() {
        if (!this.graphData || !this.ctx) {
            return;
        }
        
        const ctx = this.ctx;
        const { nodes, edges } = this.graphData;
        
        if (!nodes || !edges) {
            return;
        }

        const showNodes = this.visibility?.nodes !== false;
        const showEdges = this.visibility?.edges !== false;
        const hasSegmentFilter = Boolean(this.segmentHighlight && this.segmentHighlight.size);
        const segmentNodes = hasSegmentFilter ? this.segmentHighlight : null;
        const neighborNodes = hasSegmentFilter ? this.segmentNeighborHighlight : null;
        
      
        
        // Clear canvas
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Fondo estilo científico moderno (similar a Plotly oscuro)
        // Validar dimensiones del canvas antes de crear gradiente
        const canvasWidth = this.canvas.width || 800;
        const canvasHeight = this.canvas.height || 600;
        const centerX = canvasWidth / 2;
        const centerY = canvasHeight / 2;
        const radius = canvasWidth / 1.5;
        
        // Validar que todos los valores sean finitos
        if (isFinite(centerX) && isFinite(centerY) && isFinite(radius) && radius > 0) {
            const gradient = ctx.createRadialGradient(
                centerX, centerY, 0,
                centerX, centerY, radius
            );
            gradient.addColorStop(0, '#1e1e2e');
            gradient.addColorStop(0.5, '#181825');
            gradient.addColorStop(1, '#0f0f1a');
            ctx.fillStyle = gradient;
        } else {
            // Fallback a color sólido si hay problema
            ctx.fillStyle = '#1e1e2e';
        }
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);
        
        // Optional: Add subtle grid pattern for depth
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
        ctx.lineWidth = 1;
        for (let i = 0; i < canvasWidth; i += 50) {
            ctx.beginPath();
            ctx.moveTo(i, 0);
            ctx.lineTo(i, canvasHeight);
            ctx.stroke();
        }
        for (let i = 0; i < canvasHeight; i += 50) {
            ctx.beginPath();
            ctx.moveTo(0, i);
            ctx.lineTo(canvasWidth, i);
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
        
        if (showEdges) {
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
                const touchesSegment = hasSegmentFilter && segmentNodes && (segmentNodes.has(edge.i) || segmentNodes.has(edge.j));
                const isSegmentEdge = touchesSegment && segmentNodes && segmentNodes.has(edge.i) && segmentNodes.has(edge.j);
                const mutedBySegment = hasSegmentFilter && !touchesSegment;

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
                } else if (isSegmentEdge) {
                    lineWidth = 4.2;
                    opacity = 0.95;
                    color = `rgba(34, 197, 94, ${opacity})`;
                } else if (touchesSegment) {
                    lineWidth = 3.5;
                    opacity = 0.85;
                    color = `rgba(16, 185, 129, ${opacity})`;
                } else if (mutedBySegment) {
                    lineWidth = 1.2;
                    opacity = 0.12;
                    color = `rgba(99, 179, 237, ${opacity})`;
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
        }
        
        // Draw nodes - SIMILAR A PLOTLY CON HOVER + SELECTION HIGHLIGHT
        if (showNodes) {
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
                const inSegment = hasSegmentFilter && segmentNodes && segmentNodes.has(idx);
                const nearSegment = hasSegmentFilter && !inSegment && neighborNodes && neighborNodes.has(idx);
                const dimBySegment = hasSegmentFilter && !inSegment && !nearSegment && !isSelected && !isHovered;
                
                const selectedScale = isSelected ? 1.6 : 1.0;
                const hoverScale = isHovered ? 1.4 : 1.0;
                const neighbourScale = (isNeighborOfSelected || isNeighborOfHovered) ? 1.2 : 1.0;
                const finalSize = size * selectedScale * hoverScale * neighbourScale;
                
                // Depth factor for color
                const depthFactor = Math.max(0.3, Math.min(1, (p.z + 150) / 300));
                
                // Validar que finalSize sea válido y finito
                const validSize = (isFinite(finalSize) && finalSize > 0) ? finalSize : 5;
                const validX = isFinite(p.x) ? p.x : 0;
                const validY = isFinite(p.y) ? p.y : 0;
                
                // Create radial gradient for 3D sphere effect
                const gradient = ctx.createRadialGradient(
                    validX - validSize * 0.3, validY - validSize * 0.3, 0,
                    validX, validY, validSize
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
                } else if (inSegment) {
                    gradient.addColorStop(0, 'rgba(34, 197, 94, 1)');
                    gradient.addColorStop(0.7, 'rgba(16, 185, 129, 0.95)');
                    gradient.addColorStop(1, 'rgba(5, 150, 105, 0.85)');
                } else if (nearSegment) {
                    gradient.addColorStop(0, 'rgba(251, 191, 36, 1)');
                    gradient.addColorStop(0.7, 'rgba(245, 158, 11, 0.9)');
                    gradient.addColorStop(1, 'rgba(217, 119, 6, 0.8)');
                } else {
                    // Color por clasificación (átomo/residuo)
                    const base = this.projectedNodes[idx].color;
                    const [r, g, b] = base;
                    const dimFactor = dimBySegment ? 0.35 : 1;
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${0.95 * dimFactor})`);
                    gradient.addColorStop(0.7, `rgba(${Math.max(0,r-30)}, ${Math.max(0,g-20)}, ${Math.max(0,b-30)}, ${0.9 * dimFactor})`);
                    gradient.addColorStop(1, `rgba(${Math.max(0,r-60)}, ${Math.max(0,g-40)}, ${Math.max(0,b-60)}, ${0.75 * dimFactor})`);
                }
                
                // Draw node con valores validados
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(validX, validY, validSize, 0, Math.PI * 2);
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
                } else if (inSegment) {
                    borderWidth = 3.0;
                    borderColor = 'rgba(16, 185, 129, 0.95)';
                } else if (nearSegment) {
                    borderWidth = 2.6;
                    borderColor = 'rgba(245, 158, 11, 0.9)';
                } else if (isNeighborOfSelected || isNeighborOfHovered) {
                    borderWidth = 2.0;
                    borderColor = 'rgba(255, 220, 100, 0.9)';
                }
                
                ctx.strokeStyle = borderColor;
                ctx.lineWidth = borderWidth;
                ctx.stroke();

                
                // Inner glow sutil
                if (!isHovered && !inSegment) {
                    ctx.strokeStyle = `rgba(255, 200, 255, ${0.3 + depthFactor * 0.2})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, finalSize * 0.5, 0, Math.PI * 2);
                    ctx.stroke();
                }
            }
        }
        
        // Draw info panel - LIMPIO Y PROFESIONAL
        const padding = 14;
        const lineHeight = 22;
        const panelWidth = 280;
        const panelHeight = 80;
        
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
        ctx.fillText(` Nodos: ${nodes.length} | Aristas: ${edges.length}`, padding + 6, padding + lineHeight);
        
        ctx.font = '13px "Segoe UI", Arial, sans-serif';
        // Calcular zoom de manera inversamente proporcional a la distancia
        // Usar baselineDistance como referencia CONSTANTE
        const zoomPercent = Math.round((this.baselineDistance / this.camera.distance) * 100);
        const displayZoom = Math.max(10, Math.min(1000, zoomPercent));
        ctx.fillText(` Zoom: ${displayZoom}%`, padding + 6, padding + lineHeight * 2);
        
        ctx.fillStyle = 'rgba(180, 220, 255, 0.85)';
        ctx.font = '12px "Segoe UI", Arial, sans-serif';
        ctx.fillText(' Arrastrar para rotar | Hover en nodo para info', padding + 6, padding + lineHeight * 3);
    }
    
    /**
     * Clear the graph
     */
    clear() {
        this.graphData = null;
        this.segmentHighlight = null;
        this.segmentNeighborHighlight = null;
        this.activeSegmentId = null;
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

    setVisibility(options = {}) {
        this.visibility = {
            nodes: options.nodes !== undefined ? options.nodes : this.visibility.nodes,
            edges: options.edges !== undefined ? options.edges : this.visibility.edges
        };
        this.render();
    }

    // === Utility: color mapping based on atom/residue classification ===
    nodeColor(node) {
        const type = node.element || node.type || null;
        const label = node.label || '';
        const parts = typeof label === 'string' ? label.split(':') : [];
        const atomName = parts.length >= 4 ? parts[3] : null;

        const cpk = {
            H: [255, 255, 255],
            C: [80, 80, 80],
            N: [48, 80, 248],
            O: [255, 13, 13],
            S: [255, 200, 50],
            P: [255, 165, 0]
        };
        if (type && cpk[type]) return cpk[type];

        const aminoAcidPalette = {
            A: [148, 163, 84],
            G: [120, 143, 71],
            V: [102, 110, 45],
            L: [114, 102, 76],
            I: [136, 109, 63],
            F: [101, 73, 150],
            W: [65, 45, 122],
            M: [217, 119, 6],
            P: [248, 113, 113],
            S: [14, 165, 233],
            T: [6, 182, 212],
            Y: [233, 214, 107],
            N: [34, 197, 94],
            C: [253, 224, 71],
            Q: [45, 212, 191],
            K: [37, 99, 235],
            R: [29, 78, 216],
            H: [244, 114, 182],
            D: [239, 68, 68],
            E: [244, 63, 94]
        };

        const threeLetterToSingle = {
            ALA: 'A', ARG: 'R', ASN: 'N', ASP: 'D', CYS: 'C', GLN: 'Q', GLU: 'E', GLY: 'G', HIS: 'H',
            ILE: 'I', LEU: 'L', LYS: 'K', MET: 'M', PHE: 'F', PRO: 'P', SER: 'S', THR: 'T', TRP: 'W',
            TYR: 'Y', VAL: 'V'
        };

        const residue = (parts.length >= 2 ? parts[1] : '').toUpperCase();
        const normalizedResidue = threeLetterToSingle[residue] || residue;
        if (normalizedResidue && aminoAcidPalette[normalizedResidue]) {
            return aminoAcidPalette[normalizedResidue];
        }

        if (atomName === 'CA') return [255, 105, 180];

        return [210, 120, 210];
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.MolstarGraphRenderer = MolstarGraphRenderer;
}
