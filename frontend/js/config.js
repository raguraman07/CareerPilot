// CareerPilot AI — Central API & Environment Configuration
export const RENDER_BACKEND_URL = "https://careerpilot-txa0.onrender.com";

export const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:5000'
    : RENDER_BACKEND_URL;

// Ensure global accessibility
window.API_BASE_URL = API_BASE_URL;
