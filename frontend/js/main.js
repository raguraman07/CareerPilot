/**
 * CareerPilot AI - Main Javascript Handler
 * Handles global interactions: Light theme enforcement, Mobile Drawer Navigation, Profile Dropdowns, and Page Transitions.
 */

// -------------------------------------------------------------
// Enforce Light Theme Early (Dark Theme Removed)
// -------------------------------------------------------------
(function enforceLightThemeEarly() {
    try {
        localStorage.removeItem('theme');
        document.documentElement.classList.remove('dark-mode');
        if (document.body) document.body.classList.remove('dark-mode');
    } catch (e) {
        // Silently fail if localStorage is disabled
    }
})();

// Page entrance & exit transition manager
const setupPageTransitions = () => {
    const triggerEntrance = () => {
        document.body.classList.remove('page-exiting');
        document.body.classList.add('page-loaded');
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', triggerEntrance);
    } else {
        triggerEntrance();
    }

    window.addEventListener('pageshow', () => {
        triggerEntrance();
    });

    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        const target = link.getAttribute('target');

        if (
            !href ||
            href.startsWith('#') ||
            href.startsWith('javascript:') ||
            href.startsWith('mailto:') ||
            href.startsWith('tel:') ||
            target === '_blank' ||
            link.hasAttribute('download') ||
            link.classList.contains('logout-trigger') ||
            link.hasAttribute('data-no-transition')
        ) {
            return;
        }

        const isInternal = href.endsWith('.html') || (!href.includes('://') && !href.startsWith('//'));
        if (isInternal) {
            const currentPath = window.location.pathname.split('/').pop() || 'index.html';
            const targetPath = href.split('/').pop() || 'index.html';
            
            if (currentPath === targetPath && !href.includes('#')) {
                e.preventDefault();
                return;
            }

            e.preventDefault();
            document.body.classList.remove('page-loaded');
            document.body.classList.add('page-exiting');

            setTimeout(() => {
                window.location.href = href;
            }, 180);
        }
    });
};

setupPageTransitions();

document.addEventListener('DOMContentLoaded', () => {
    // Enforce light theme state on DOM load
    document.documentElement.classList.remove('dark-mode');
    document.body.classList.remove('dark-mode');
    
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        // Hide theme toggle button since only light theme is used
        themeToggleBtn.style.display = 'none';
    }

    // -------------------------------------------------------------
    // Dashboard Mobile Drawer & Profile Dropdown
    // -------------------------------------------------------------
    const sidebar = document.getElementById('sidebar-wrapper');
    const hamburgerBtn = document.getElementById('hamburger-menu-btn') || document.getElementById('sidebar-open-btn');
    const closeSidebarBtn = document.getElementById('sidebar-close-btn');
    const overlay = document.getElementById('sidebar-overlay');

    const openDrawer = () => {
        if (sidebar) sidebar.classList.add('open');
        if (overlay) overlay.classList.add('active');
        if (hamburgerBtn) hamburgerBtn.setAttribute('aria-expanded', 'true');
    };

    const closeDrawer = () => {
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
        if (hamburgerBtn) hamburgerBtn.setAttribute('aria-expanded', 'false');
    };

    if (hamburgerBtn) hamburgerBtn.addEventListener('click', openDrawer);
    if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeDrawer);
    if (overlay) overlay.addEventListener('click', closeDrawer);

    // Profile Avatar Dropdown
    const profileBtn = document.getElementById('profile-dropdown-btn');
    const profileDropdown = document.getElementById('profile-dropdown');

    if (profileBtn && profileDropdown) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = profileDropdown.classList.contains('show');
            profileDropdown.classList.toggle('show', !isOpen);
            profileBtn.setAttribute('aria-expanded', !isOpen);
        });

        document.addEventListener('click', (e) => {
            if (!profileDropdown.contains(e.target) && !profileBtn.contains(e.target)) {
                profileDropdown.classList.remove('show');
                profileBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // -------------------------------------------------------------
    // Landing Page Nav Toggle (If Present)
    // -------------------------------------------------------------
    const menuToggle = document.getElementById('menu-toggle');
    const navLinksList = document.querySelector('.nav-links');
    
    if (menuToggle && navLinksList) {
        menuToggle.addEventListener('click', () => {
            const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
            menuToggle.setAttribute('aria-expanded', !isExpanded);
            navLinksList.classList.toggle('active');
            menuToggle.classList.toggle('menu-open');
        });

        document.addEventListener('click', (e) => {
            if (!navLinksList.contains(e.target) && !menuToggle.contains(e.target) && navLinksList.classList.contains('active')) {
                navLinksList.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');
                menuToggle.classList.remove('menu-open');
            }
        });
    }
});
