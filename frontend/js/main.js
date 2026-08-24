/**
 * CareerPilot AI - Main Javascript Handler
 * Handles global interactions: Theme toggling, Mobile Navigation, Smooth Page Transitions, Scroll animations, and active state tracking.
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
    // Reveal body cleanly on load
    const triggerEntrance = () => {
        document.body.classList.remove('page-exiting');
        document.body.classList.add('page-loaded');
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', triggerEntrance);
    } else {
        triggerEntrance();
    }

    // Handle bfcache (browser back / forward button navigation)
    window.addEventListener('pageshow', (event) => {
        triggerEntrance();
    });

    // Intercept internal page navigation clicks for smooth fade-out
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        const target = link.getAttribute('target');

        // Skip non-navigational, external, mailto, anchor or new-tab links
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

        // Determine if target URL is an internal HTML page
        const isInternal = href.endsWith('.html') || (!href.includes('://') && !href.startsWith('//'));
        if (isInternal) {
            // Check if navigating to current exact page
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
            }, 200);
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
    
    // Determine initial theme
    const getInitialTheme = () => {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme) {
            return storedTheme;
        }
        return systemPrefersDark.matches ? 'dark' : 'light';
    };

    // Apply theme helper
    const applyTheme = (theme) => {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark-mode');
            document.body.classList.add('dark-mode');
        } else {
            document.documentElement.classList.remove('dark-mode');
            document.body.classList.remove('dark-mode');
        }
        localStorage.setItem('theme', theme);
        
        // Update aria label and icon accessibility
        if (themeToggleBtn) {
            themeToggleBtn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        }
    };

    // Initialize Theme
    const currentTheme = getInitialTheme();
    applyTheme(currentTheme);

    // Toggle click event
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const isDark = document.body.classList.contains('dark-mode');
            applyTheme(isDark ? 'light' : 'dark');
        });
    }

    // Listen for system theme change events
    systemPrefersDark.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    });

    // -------------------------------------------------------------
    // 2. Mobile Navigation Menu Toggle
    // -------------------------------------------------------------
    const menuToggle = document.getElementById('menu-toggle');
    const navLinksList = document.querySelector('.nav-links');
    
    if (menuToggle && navLinksList) {
        menuToggle.addEventListener('click', () => {
            const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
            menuToggle.setAttribute('aria-expanded', !isExpanded);
            navLinksList.classList.toggle('active');
            
            // Toggle visual state of button (e.g. Hamburger to Close transition class)
            menuToggle.classList.toggle('menu-open');
        });

        // Close mobile menu when clicking outside or on a link
        document.addEventListener('click', (e) => {
            if (!navLinksList.contains(e.target) && !menuToggle.contains(e.target) && navLinksList.classList.contains('active')) {
                navLinksList.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');
                menuToggle.classList.remove('menu-open');
            }
        });

        navLinksList.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinksList.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');
                menuToggle.classList.remove('menu-open');
            });
        });
    }

    // -------------------------------------------------------------
    // 3. Scroll Reveal Animations (Intersection Observer)
    // -------------------------------------------------------------
    const revealElements = document.querySelectorAll('.feature-card, .benefit-card, .cta-banner, .hero-content');
    
    const revealOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const revealOnScroll = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                observer.unobserve(entry.target); // Animates only once
            }
        });
    }, revealOptions);

    revealElements.forEach(element => {
        // Setup initial animation classes
        element.classList.add('reveal-init');
        revealOnScroll.observe(element);
    });

    // Add required reveal CSS dynamically to avoid breaking layout without JS
    const style = document.createElement('style');
    style.innerHTML = `
        .reveal-init {
            opacity: 0;
            transform: translateY(30px);
            transition: opacity 0.8s cubic-bezier(0.4, 0, 0.2, 1), transform 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .reveal-init.revealed {
            opacity: 1;
            transform: translateY(0);
        }
        @media (prefers-reduced-motion: reduce) {
            .reveal-init {
                opacity: 1 !important;
                transform: none !important;
                transition: none !important;
            }
        }
    `;
    document.head.appendChild(style);

    // -------------------------------------------------------------
    // 4. Smooth Navigation Scroll Spy
    // -------------------------------------------------------------
    const sections = document.querySelectorAll('section[id]');
    const navItems = document.querySelectorAll('.nav-link[href^="#"]');

    const scrollSpyOptions = {
        threshold: 0.3,
        rootMargin: '-70px 0px 0px 0px' // Offset header height
    };

    const scrollSpyCallback = (entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                navItems.forEach(item => {
                    if (item.getAttribute('href') === `#${id}`) {
                        item.classList.add('active');
                        item.setAttribute('aria-current', 'page');
                    } else {
                        item.classList.remove('active');
                        item.removeAttribute('aria-current');
                    }
                });
            }
        });
    };

    const scrollSpyObserver = new IntersectionObserver(scrollSpyCallback, scrollSpyOptions);
    sections.forEach(section => scrollSpyObserver.observe(section));
});
