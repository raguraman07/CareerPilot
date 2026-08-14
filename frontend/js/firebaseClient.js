// CareerPilot AI - Firebase Client Initialization
// Imported via CDN as ES Modules for native browser support
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js';
import { getAuth } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';
import { getAnalytics } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-analytics.js';

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyCYtZw8J5CNc7X4CAlLeKP2NNqsUnECgZM",
    authDomain: "careerpilot-4e3a5.firebaseapp.com",
    projectId: "careerpilot-4e3a5",
    storageBucket: "careerpilot-4e3a5.firebasestorage.app",
    messagingSenderId: "200837641514",
    appId: "1:200837641514:web:421ffa389e741152085a53",
    measurementId: "G-CFH8GR1GY4"
};

// Initialize Firebase App
export const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication Service
export const auth = getAuth(app);

// Initialize Firebase Analytics safely
let analyticsInstance = null;
try {
    if (typeof window !== 'undefined' && firebaseConfig.measurementId) {
        analyticsInstance = getAnalytics(app);
    }
} catch (e) {
    console.warn("[Firebase] Analytics disabled or unsupported in current environment.");
}
export const analytics = analyticsInstance;