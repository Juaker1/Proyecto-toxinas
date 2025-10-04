/**
 * NAVBAR - Sistema de navegación unificado
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeNavbar();
});

function initializeNavbar() {
    // Marcar página activa
    setActivePage();
    
    // Toggle móvil
    setupMobileToggle();
    
    // Smooth scroll
    setupSmoothScroll();
}

/**
 * Marca la página activa en el navbar
 */
function setActivePage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const linkPath = new URL(link.href).pathname;
        
        if (currentPath === linkPath || 
            (currentPath.includes(linkPath) && linkPath !== '/')) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

/**
 * Setup del toggle para móvil
 */
function setupMobileToggle() {
    const toggle = document.querySelector('.navbar-toggle');
    const nav = document.querySelector('.navbar-nav');
    
    if (!toggle || !nav) return;
    
    toggle.addEventListener('click', function() {
        nav.classList.toggle('mobile-open');
        
        // Cambiar icono
        const icon = this.querySelector('i') || this;
        if (nav.classList.contains('mobile-open')) {
            icon.textContent = '✕';
        } else {
            icon.textContent = '☰';
        }
    });
    
    // Cerrar menú al hacer click en un link
    const navLinks = nav.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            nav.classList.remove('mobile-open');
            toggle.querySelector('i').textContent = '☰';
        });
    });
}

/**
 * Smooth scroll para anclas
 */
function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            
            if (target) {
                const offset = 100; // Espacio para el navbar
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Añadir efecto de scroll al navbar
 */
window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.main-navbar');
    if (!navbar) return;
    
    if (window.scrollY > 50) {
        navbar.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15)';
    } else {
        navbar.style.boxShadow = '';
    }
});
