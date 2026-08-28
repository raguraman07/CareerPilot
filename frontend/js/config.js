// CareerPilot AI — Central API & Environment Configuration
export const API_BASE_URL = 'http://127.0.0.1:5000';

// Ensure global accessibility
if (typeof window !== 'undefined') {
    window.API_BASE_URL = API_BASE_URL;
}
