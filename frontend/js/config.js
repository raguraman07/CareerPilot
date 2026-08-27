// CareerPilot AI — Central API & Environment Configuration
// In production (e.g. hosted on Vercel), replace YOUR-BACKEND with your Render service URL:
// Example: export const PRODUCTION_BACKEND_URL = "https://careerpilot-backend.onrender.com";
export const PRODUCTION_BACKEND_URL = "https://YOUR-CAREERPILOT-BACKEND.onrender.com";

const isLocalhost = (
    typeof window !== 'undefined' && (
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === '' ||
        window.location.protocol === 'file:'
    )
);

export const API_BASE_URL = isLocalhost
    ? 'http://127.0.0.1:5000'
    : (window.__CAREERPILOT_BACKEND_URL__ || PRODUCTION_BACKEND_URL);

// Ensure global accessibility
if (typeof window !== 'undefined') {
    window.API_BASE_URL = API_BASE_URL;
}
