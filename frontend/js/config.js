// CareerPilot AI — Central API & Environment Configuration

// Production Render Backend URL
export const PRODUCTION_BACKEND_URL = "https://careerpilot-backend-787d.onrender.com";

// Determine whether running locally or in production (Vercel / custom domain)
const isLocalEnvironment = (
    typeof window !== 'undefined' && (
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === '' ||
        window.location.protocol === 'file:'
    )
);

// In local development, use localhost Flask server.
// In production (Vercel), use the deployed Render backend URL.
export const API_BASE_URL = isLocalEnvironment
    ? 'http://127.0.0.1:5000'
    : (window.__CAREERPILOT_BACKEND_URL__ || PRODUCTION_BACKEND_URL);

// Ensure global accessibility for all modules
if (typeof window !== 'undefined') {
    window.API_BASE_URL = API_BASE_URL;
}
