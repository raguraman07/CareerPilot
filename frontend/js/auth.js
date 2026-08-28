// CareerPilot AI - Authentication JS Handlers using Firebase Auth Client
import { auth } from './firebaseClient.js';
import {
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    updateProfile,
    signOut,
    onAuthStateChanged,
    sendPasswordResetEmail,
    confirmPasswordReset,
    updatePassword,
    GoogleAuthProvider,
    signInWithPopup
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';

import { API_BASE_URL } from './config.js';

// Automatically redirect 127.0.0.1 to localhost for local testing
if (typeof window !== 'undefined' && window.location.hostname === '127.0.0.1') {
    const normalizedUrl = new URL(window.location.href);
    normalizedUrl.hostname = 'localhost';
    window.location.replace(normalizedUrl.toString());
}

// -------------------------------------------------------------
// Helper: Path & Page Classification (Vercel & Clean URL Safe)
// -------------------------------------------------------------
export function getPageName() {
    if (typeof window === 'undefined') return '';
    const pathname = window.location.pathname.toLowerCase();
    const segment = pathname.split('/').filter(Boolean).pop() || 'index';
    return segment.replace(/\.html$/, '');
}

export function isAuthPage() {
    const page = getPageName();
    return ['login', 'register', 'forgot-password', 'reset-password'].includes(page);
}

export function isPublicPage() {
    const page = getPageName();
    return ['index', '', 'login', 'register', 'forgot-password', 'reset-password'].includes(page);
}

// User-facing error message mapper for Firebase Auth
export function mapFirebaseError(error) {
    if (!error) return "";
    const code = error.code || "";
    const msg = (error.message || "").toLowerCase();
    console.error("Firebase auth error details:", { code, message: error.message, fullError: error });

    if (code === 'auth/invalid-credential' || code === 'auth/user-not-found' || code === 'auth/wrong-password' || msg.includes('invalid credential') || msg.includes('invalid-credential')) {
        return "Invalid email or password. Please double check and try again.";
    }
    if (code === 'auth/email-already-in-use' || msg.includes('email already in use')) {
        return "An account with this email address already exists. Please sign in instead.";
    }
    if (code === 'auth/weak-password' || msg.includes('weak password')) {
        return "Password is too weak. Please choose a stronger password (minimum 6 characters).";
    }
    if (code === 'auth/invalid-email' || msg.includes('invalid email')) {
        return "Please enter a valid email address.";
    }
    if (code === 'auth/operation-not-allowed') {
        return "Firebase Email/Password authentication is not enabled. Please enable it in Firebase Console.";
    }
    if (code === 'auth/unauthorized-domain') {
        return `Firebase Domain Authorization: Domain (${window.location.hostname}) must be added to Firebase Console -> Authentication -> Settings -> Authorized domains.`;
    }
    if (code === 'auth/invalid-api-key') {
        return "Firebase Config Error: Invalid API key. Please check firebaseClient.js.";
    }
    if (code === 'auth/user-disabled') {
        return "This account has been disabled. Please contact support.";
    }
    if (code === 'auth/popup-closed-by-user') {
        return "Sign-in popup was closed before completing authentication.";
    }
    if (code === 'auth/too-many-requests') {
        return "Too many failed attempts. Access to this account has been temporarily disabled. Please try again later or reset your password.";
    }
    if (code === 'auth/network-request-failed') {
        return "Network connection error. Please check your internet connection.";
    }
    return error.message || "An authentication error occurred. Please try again.";
}

// Debug Logging Helper
function logAuth(message, data = null) {
    if (data !== null) {
        console.log(`[Auth System] ${message}`, data);
    } else {
        console.log(`[Auth System] ${message}`);
    }
}

// Track redirection to prevent loop / race conditions
let isRedirecting = false;

function safeRedirect(targetUrl) {
    if (isRedirecting) return;
    isRedirecting = true;
    logAuth(`Navigating to target: ${targetUrl}`);
    window.location.href = targetUrl;
}

// Helper to wait for Firebase to resolve initial Auth state
export function getCurrentFirebaseUser() {
    return new Promise((resolve) => {
        const unsubscribe = onAuthStateChanged(auth, (user) => {
            unsubscribe();
            resolve(user);
        });
    });
}

// -------------------------------------------------------------
// 1. Page Guards & Session Management
// -------------------------------------------------------------

/**
 * Checks for an active Firebase session on protected pages.
 * Redirects to login.html only if no active user session exists.
 */
export async function requireAuth() {
    try {
        logAuth('Checking active session via Firebase Auth...');
        const user = await getCurrentFirebaseUser();
        
        if (!user) {
            logAuth('Redirect reason: No active Firebase user found. Redirecting to login.html');
            safeRedirect('login.html');
            return null;
        }
        
        logAuth('Session found / restored successfully:', { uid: user.uid, email: user.email });
        
        let fullName = user.displayName || (user.email ? user.email.split('@')[0] : "User");
        let token = null;

        try {
            token = await user.getIdToken();
            // Sync with backend with a fast abort timeout to avoid blocking during Render cold starts
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3500);

            const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                signal: controller.signal
            }).catch(e => {
                logAuth('Backend profile fetch timed out or offline:', e.message);
                return null;
            });
            clearTimeout(timeoutId);
            
            if (response && response.ok) {
                const result = await response.json();
                if (result.user?.full_name) {
                    fullName = result.user.full_name;
                }
                logAuth('Backend profile sync succeeded.');
            }
        } catch (fetchErr) {
            logAuth('Backend profile sync note:', fetchErr.message);
        }
        
        return {
            user: {
                id: user.uid,
                email: user.email,
                full_name: fullName
            },
            firebaseUser: user,
            token
        };
    } catch (e) {
        logAuth("Auth check error:", e);
        safeRedirect('login.html');
        return null;
    }
}

/**
 * Helper to retrieve the active Firebase ID token.
 */
export async function getAuthToken() {
    try {
        const user = await getCurrentFirebaseUser();
        if (user) {
            return await user.getIdToken();
        }
    } catch (e) {
        logAuth("Error retrieving Firebase ID Token:", e);
    }
    return null;
}

/**
 * Helper to determine redirect destination based on query param or default dashboard
 */
export function determinePostAuthDestination(explicitRedirect = null) {
    if (explicitRedirect) {
        const clean = explicitRedirect.trim();
        if (/^[a-zA-Z0-9_\-]+\.html$/.test(clean)) {
            return clean;
        } else if (/^[a-zA-Z0-9_\-]+$/.test(clean)) {
            return `${clean}.html`;
        }
    }
    return 'dashboard.html';
}

/**
 * Redirects authenticated users from auth pages to dashboard.html
 */
export async function redirectIfAuthenticated() {
    try {
        const user = await getCurrentFirebaseUser();
        if (user) {
            const params = new URLSearchParams(window.location.search);
            const target = determinePostAuthDestination(params.get('redirect'));
            logAuth(`Redirect reason: Authenticated user on auth page. Redirecting to ${target}`);
            safeRedirect(target);
            return true;
        }
    } catch (e) {
        logAuth('Error checking auth state for redirect:', e);
    }
    return false;
}

/**
 * Signs out the current user via Firebase and redirects to login.html.
 */
export async function logoutUser() {
    logAuth('Initiating user logout via Firebase...');
    try {
        await signOut(auth);
    } catch (e) {
        logAuth("Error during Firebase signOut:", e);
    } finally {
        logAuth('Redirect reason: User explicitly logged out. Redirecting to login.html');
        safeRedirect('login.html');
    }
}

/**
 * Signs in user with Google OAuth via Firebase Popup.
 */
export async function signInWithGoogle() {
    logAuth('Initiating Google OAuth login via Firebase...');
    const provider = new GoogleAuthProvider();
    try {
        const result = await signInWithPopup(auth, provider);
        logAuth('Google OAuth sign-in successful:', result.user?.email);
        
        // Sync with backend in background
        try {
            const token = await result.user.getIdToken();
            fetch(`${API_BASE_URL}/api/auth/signup`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ full_name: result.user.displayName || "" })
            }).catch(() => {});
        } catch (e) {}

        const params = new URLSearchParams(window.location.search);
        const target = determinePostAuthDestination(params.get('redirect'));
        safeRedirect(target);
        return result;
    } catch (error) {
        logAuth('Google OAuth error:', error);
        throw error;
    }
}

// -------------------------------------------------------------
// Setup Global Auth State Listener
// -------------------------------------------------------------
onAuthStateChanged(auth, async (user) => {
    logAuth(`Auth state event triggered:`, user ? user.email : 'No user');
    
    if (user) {
        logAuth('Login success: Valid Firebase session for user:', user.email);
        if (isAuthPage()) {
            const params = new URLSearchParams(window.location.search);
            const target = determinePostAuthDestination(params.get('redirect'));
            logAuth(`Active session detected on auth page. Redirecting to ${target}`);
            safeRedirect(target);
        }
    } else {
        logAuth('User signed out or no active session.');
        if (!isPublicPage()) {
            logAuth('Signed out on protected page. Redirecting to login.html');
            safeRedirect('login.html');
        }
    }
});

// -------------------------------------------------------------
// 2. Client-side Form Validation & Inputs Helpers
// -------------------------------------------------------------
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email) {
    if (!email) return "Email address is required.";
    if (!emailRegex.test(email)) return "Please enter a valid email address.";
    return null;
}

export function validatePassword(password) {
    if (!password) return "Password is required.";
    if (password.length < 6) return "Password must be at least 6 characters long.";
    return null;
}

export function setErrorState(inputEl, errorMessage) {
    if (!inputEl) return;
    const groupEl = inputEl.closest('.form-group') || inputEl.parentElement;
    if (!groupEl) return;
    
    if (errorMessage) {
        groupEl.classList.add('has-error');
        inputEl.classList.add('input-error');
        let feedbackEl = groupEl.querySelector('.invalid-feedback');
        if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'invalid-feedback';
            groupEl.appendChild(feedbackEl);
        }
        feedbackEl.textContent = errorMessage;
    } else {
        groupEl.classList.remove('has-error');
        inputEl.classList.remove('input-error');
        const feedbackEl = groupEl.querySelector('.invalid-feedback');
        if (feedbackEl) feedbackEl.remove();
    }
}

// -------------------------------------------------------------
// 3. Loading Spinner & Button Controls
// -------------------------------------------------------------
export function setButtonLoading(buttonEl, isLoading, loadingText = "Processing...") {
    if (!buttonEl) return;
    
    if (isLoading) {
        buttonEl.disabled = true;
        if (!buttonEl.dataset.originalText) {
            buttonEl.dataset.originalText = buttonEl.innerHTML;
        }
        buttonEl.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>${loadingText}</span>`;
    } else {
        buttonEl.disabled = false;
        if (buttonEl.dataset.originalText) {
            buttonEl.innerHTML = buttonEl.dataset.originalText;
        }
    }
}

// -------------------------------------------------------------
// 4. Alert & Message Banners
// -------------------------------------------------------------
export function showFormBanner(containerEl, message, type = 'error') {
    if (!containerEl) return;

    // Check for existing alert box in card
    const alertBox = document.getElementById('auth-alert-box') || containerEl.querySelector('.alert-box');
    const existingBanner = containerEl.querySelector('.form-banner');
    if (existingBanner) existingBanner.remove();
    
    if (!message) {
        if (alertBox) {
            alertBox.style.display = 'none';
            alertBox.textContent = '';
        }
        return;
    }
    
    const banner = document.createElement('div');
    banner.className = `form-banner form-banner--${type}`;
    banner.setAttribute('role', 'alert');
    
    let iconSvg = '';
    if (type === 'error') {
        iconSvg = `<svg class="form-banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        iconSvg = `<svg class="form-banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    }
    
    banner.innerHTML = `
        ${iconSvg}
        <div class="form-banner-content">${message}</div>
    `;
    
    containerEl.prepend(banner);
}

// -------------------------------------------------------------
// 5. Password Strength Meter
// -------------------------------------------------------------
export function checkPasswordStrength(password) {
    if (!password) return { score: 0, label: "", class: "" };
    
    let score = 0;
    if (password.length >= 6) score += 1;
    if (password.length >= 10) score += 1;
    if (/[a-zA-Z]/.test(password) && /[0-9]/.test(password)) score += 1;
    if (/[^a-zA-Z0-9]/.test(password) || (/[a-z]/.test(password) && /[A-Z]/.test(password))) score += 1;
    
    if (password.length < 6) {
        return { score: 1, label: "Too short (min 6 characters)", class: "strength-weak" };
    }
    
    if (score <= 2) {
        return { score: 1, label: "Weak password", class: "strength-weak" };
    } else if (score === 3) {
        return { score: 2, label: "Medium strength", class: "strength-medium" };
    } else {
        return { score: 3, label: "Strong password", class: "strength-strong" };
    }
}

// -------------------------------------------------------------
// 6. Global DOM Listeners & Initializers
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Password visibility toggles
    document.querySelectorAll('.password-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const wrapper = btn.closest('.input-wrapper');
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (!input) return;
            
            if (input.type === 'password') {
                input.type = 'text';
                btn.setAttribute('aria-label', 'Hide password');
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`;
            } else {
                input.type = 'password';
                btn.setAttribute('aria-label', 'Show password');
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
            }
        });
    });

    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const forgotForm = document.getElementById('forgot-password-form') || document.getElementById('forgot-form');
    const resetForm = document.getElementById('reset-password-form') || document.getElementById('reset-form');

    // -------------------------------------------------------------
    // Login Form Handler
    // -------------------------------------------------------------
    if (loginForm) {
        redirectIfAuthenticated();
        
        const emailInput = document.getElementById('email');
        const passwordInput = document.getElementById('password');
        const submitBtn = loginForm.querySelector('button[type="submit"]') || document.getElementById('btn-login');

        if (emailInput) {
            emailInput.addEventListener('blur', () => {
                setErrorState(emailInput, validateEmail(emailInput.value.trim()));
            });
            emailInput.addEventListener('input', () => {
                if (emailInput.classList.contains('input-error')) {
                    setErrorState(emailInput, null);
                }
            });
        }

        if (passwordInput) {
            passwordInput.addEventListener('input', () => {
                if (passwordInput.classList.contains('input-error')) {
                    setErrorState(passwordInput, null);
                }
            });
        }

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = emailInput ? emailInput.value.trim() : "";
            const password = passwordInput ? passwordInput.value : "";

            const emailErr = validateEmail(email);
            const passErr = validatePassword(password);

            if (emailInput) setErrorState(emailInput, emailErr);
            if (passwordInput) setErrorState(passwordInput, passErr);

            if (emailErr || passErr) return;

            setButtonLoading(submitBtn, true, "Signing in...");
            showFormBanner(loginForm, null);

            try {
                logAuth('Attempting signInWithEmailAndPassword for user:', email);
                const userCredential = await signInWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;
                
                logAuth('Login success: Firebase authentication succeeded for user:', user.email);

                const params = new URLSearchParams(window.location.search);
                const targetUrl = determinePostAuthDestination(params.get('redirect'));

                logAuth(`Redirecting to target page: ${targetUrl}`);
                safeRedirect(targetUrl);
            } catch (err) {
                logAuth('Login failed error:', err.message);
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(loginForm, friendlyMsg, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }

    // -------------------------------------------------------------
    // Google OAuth Buttons Event Listener Setup
    // -------------------------------------------------------------
    document.querySelectorAll('.google-auth-btn, .btn-google-auth, #btn-google-login, #btn-google-register, #google-signin-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>Connecting...</span>`;
            
            try {
                await signInWithGoogle();
            } catch (googleErr) {
                logAuth('Google sign-in error:', googleErr);
                btn.disabled = false;
                btn.innerHTML = originalHtml;
                const currentForm = btn.closest('form') || document.querySelector('form');
                if (currentForm) {
                    showFormBanner(currentForm, mapFirebaseError(googleErr), 'error');
                }
            }
        });
    });

    // -------------------------------------------------------------
    // Register Form Handler
    // -------------------------------------------------------------
    if (registerForm) {
        redirectIfAuthenticated();

        const nameInput = document.getElementById('full-name');
        const emailInput = document.getElementById('email');
        const passwordInput = document.getElementById('password');
        const confirmInput = document.getElementById('confirm-password');
        const strengthFill = document.querySelector('.password-strength-fill');
        const strengthText = document.querySelector('.password-strength-text');
        const submitBtn = registerForm.querySelector('button[type="submit"]') || document.getElementById('btn-register');

        if (passwordInput && strengthFill && strengthText) {
            passwordInput.addEventListener('input', () => {
                const password = passwordInput.value;
                const strength = checkPasswordStrength(password);
                strengthFill.className = 'password-strength-fill';
                if (strength.class) {
                    strengthFill.classList.add(strength.class);
                }
                strengthText.textContent = strength.label;
            });
        }

        if (nameInput) {
            nameInput.addEventListener('blur', () => {
                setErrorState(nameInput, nameInput.value.trim() ? null : "Full name is required.");
            });
        }
        if (emailInput) {
            emailInput.addEventListener('blur', () => {
                setErrorState(emailInput, validateEmail(emailInput.value.trim()));
            });
        }
        if (passwordInput) {
            passwordInput.addEventListener('blur', () => {
                setErrorState(passwordInput, validatePassword(passwordInput.value));
            });
        }
        if (confirmInput) {
            confirmInput.addEventListener('blur', () => {
                const matchErr = passwordInput.value === confirmInput.value ? null : "Passwords do not match.";
                setErrorState(confirmInput, matchErr);
            });
        }

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const fullName = nameInput ? nameInput.value.trim() : "";
            const email = emailInput ? emailInput.value.trim() : "";
            const password = passwordInput ? passwordInput.value : "";
            const confirmPassword = confirmInput ? confirmInput.value : "";

            const nameErr = fullName ? null : "Full name is required.";
            const emailErr = validateEmail(email);
            const passErr = validatePassword(password);
            const confirmErr = confirmInput ? (password === confirmPassword ? null : "Passwords do not match.") : null;

            if (nameInput) setErrorState(nameInput, nameErr);
            if (emailInput) setErrorState(emailInput, emailErr);
            if (passwordInput) setErrorState(passwordInput, passErr);
            if (confirmInput) setErrorState(confirmInput, confirmErr);

            if (nameErr || emailErr || passErr || confirmErr) return;

            setButtonLoading(submitBtn, true, "Creating account...");
            showFormBanner(registerForm, null);

            try {
                logAuth('Attempting createUserWithEmailAndPassword for user:', email);
                const userCredential = await createUserWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;

                // Update Firebase Auth Display Name
                await updateProfile(user, { displayName: fullName });

                // Sync account profile with Flask backend in background
                try {
                    const token = await user.getIdToken();
                    fetch(`${API_BASE_URL}/api/auth/signup`, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ full_name: fullName })
                    }).catch(() => {});
                } catch (backendErr) {}

                showFormBanner(registerForm, "Account created successfully! Redirecting...", 'success');
                registerForm.reset();
                
                const target = determinePostAuthDestination();
                safeRedirect(target);

            } catch (err) {
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(registerForm, friendlyMsg, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }

    // -------------------------------------------------------------
    // Forgot Password Form Handler
    // -------------------------------------------------------------
    if (forgotForm) {
        const emailInput = forgotForm.querySelector('#email') || document.getElementById('email');
        const submitBtn = forgotForm.querySelector('button[type="submit"]') || document.getElementById('btn-forgot');

        if (emailInput) {
            emailInput.addEventListener('blur', () => {
                setErrorState(emailInput, validateEmail(emailInput.value.trim()));
            });
        }

        forgotForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = emailInput ? emailInput.value.trim() : "";
            const emailErr = validateEmail(email);

            if (emailInput) setErrorState(emailInput, emailErr);
            if (emailErr) return;

            setButtonLoading(submitBtn, true, "Sending email...");
            showFormBanner(forgotForm, null);

            try {
                logAuth('Sending password reset email via Firebase to:', email);
                await sendPasswordResetEmail(auth, email);
                
                showFormBanner(forgotForm, "Password reset link sent! Check your inbox.", 'success');
                forgotForm.reset();
            } catch (err) {
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(forgotForm, friendlyMsg, 'error');
            } finally {
                setButtonLoading(submitBtn, false);
            }
        });
    }

    // -------------------------------------------------------------
    // Reset Password Form Handler
    // -------------------------------------------------------------
    if (resetForm) {
        const passwordInput = resetForm.querySelector('#new-password') || resetForm.querySelector('#password') || document.getElementById('new-password') || document.getElementById('password');
        const confirmInput = resetForm.querySelector('#confirm-password') || document.getElementById('confirm-password');
        const submitBtn = resetForm.querySelector('button[type="submit"]') || document.getElementById('btn-reset');

        if (passwordInput) {
            passwordInput.addEventListener('blur', () => {
                setErrorState(passwordInput, validatePassword(passwordInput.value));
            });
        }
        if (confirmInput && passwordInput) {
            confirmInput.addEventListener('blur', () => {
                const matchErr = passwordInput.value === confirmInput.value ? null : "Passwords do not match.";
                setErrorState(confirmInput, matchErr);
            });
        }

        resetForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const password = passwordInput ? passwordInput.value : "";
            const confirmPassword = confirmInput ? confirmInput.value : "";

            const passErr = validatePassword(password);
            const confirmErr = confirmInput ? (password === confirmPassword ? null : "Passwords do not match.") : null;

            if (passwordInput) setErrorState(passwordInput, passErr);
            if (confirmInput) setErrorState(confirmInput, confirmErr);

            if (passErr || confirmErr) return;

            setButtonLoading(submitBtn, true, "Resetting password...");
            showFormBanner(resetForm, null);

            try {
                const params = new URLSearchParams(window.location.search);
                const oobCode = params.get('oobCode');

                if (oobCode) {
                    logAuth('Confirming password reset with Firebase oobCode...');
                    await confirmPasswordReset(auth, oobCode, password);
                    showFormBanner(resetForm, "Your password has been successfully updated. Redirecting to login...", 'success');
                } else if (auth.currentUser) {
                    logAuth('Updating password for current logged-in user...');
                    await updatePassword(auth.currentUser, password);
                    showFormBanner(resetForm, "Your password has been successfully updated. Redirecting to login...", 'success');
                } else {
                    throw new Error("No password reset code found in the reset link. Please request a new password reset link.");
                }

                resetForm.reset();

                setTimeout(() => {
                    safeRedirect('login.html');
                }, 2000);

            } catch (err) {
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(resetForm, friendlyMsg, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }
});