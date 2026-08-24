/**
 * CareerPilot AI - Main Javascript Handler
 * Handles global interactions: Theme toggling, Mobile Drawer Navigation, Profile Dropdowns, Scroll animations, and Active State tracking.
 */

// -------------------------------------------------------------
// Early Anti-Flicker Page Transition & Theme Helper
// -------------------------------------------------------------
(function syncThemeEarly() {
    try {
        const storedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = storedTheme || (systemPrefersDark ? 'dark' : 'light');
        if (theme === 'dark') {
            document.documentElement.classList.add('dark-mode');
            if (document.body) document.body.classList.add('dark-mode');
        } else {
            document.documentElement.classList.remove('dark-mode');
            if (document.body) document.body.classList.remove('dark-mode');
        }
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
            link.hasAttribute('download')
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
    // -------------------------------------------------------------
    // 1. Theme Manager (Light / Dark Mode)
    // -------------------------------------------------------------
    const themeToggleBtn = document.getElementById('theme-toggle');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    
    const getInitialTheme = () => {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme) return storedTheme;
        return systemPrefersDark.matches ? 'dark' : 'light';
    };

    const applyTheme = (theme) => {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark-mode');
            document.body.classList.add('dark-mode');
        } else {
            document.documentElement.classList.remove('dark-mode');
            document.body.classList.remove('dark-mode');
        }
        localStorage.setItem('theme', theme);
        
        if (themeToggleBtn) {
            themeToggleBtn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        }
    };

    applyTheme(getInitialTheme());

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const isDark = document.body.classList.contains('dark-mode');
            applyTheme(isDark ? 'light' : 'dark');
        });
    }

    systemPrefersDark.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    });

    // -------------------------------------------------------------
    // 2. Dashboard Mobile Drawer & Profile Dropdown
    // -------------------------------------------------------------
    const sidebar = document.getElementById('sidebar-wrapper');
    const hamburgerBtn = document.getElementById('hamburger-menu-btn');
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
    // 3. Landing Page Nav Toggle (If Present)
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
