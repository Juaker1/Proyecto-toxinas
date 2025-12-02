// Popup functionality
document.addEventListener('DOMContentLoaded', function() {
    const popupOverlay = document.getElementById('popup-overlay');
    const popupClose = document.getElementById('popup-close');
    const popupBtn = document.getElementById('popup-btn');

    // Check if popup has been shown in this session
    if (!sessionStorage.getItem('popupShown')) {
        // Show popup
        popupOverlay.classList.add('show');
        sessionStorage.setItem('popupShown', 'true');
    }

    // Close popup function
    function closePopup() {
        popupOverlay.classList.remove('show');
    }

    // Event listeners
    popupClose.addEventListener('click', closePopup);
    popupBtn.addEventListener('click', closePopup);

    // Close on overlay click
    popupOverlay.addEventListener('click', function(e) {
        if (e.target === popupOverlay) {
            closePopup();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && popupOverlay.classList.contains('show')) {
            closePopup();
        }
    });
});