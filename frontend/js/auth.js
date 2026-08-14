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

// Automatically redirect 127.0.0.1 to localhost for default Firebase Auth domain authorization
if (window.location.hostname === '127.0.0.1') {
    const normalizedUrl = new URL(window.location.href);
    normalizedUrl.hostname = 'localhost';
    window.location.replace(normalizedUrl.toString());
}

// Configuration: Change this to match your Flask API URL when deployed or running locally
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;


// User-facing error message mapper for Firebase Auth
function mapFirebaseError(error) {
    if (!error) return "";
    const code = error.code || "";
    const msg = (error.message || "").toLowerCase();
    console.error("Firebase auth error details:", { code, message: error.message, fullError: error });

    if (code === 'auth/invalid-credential' || code === 'auth/user-not-found' || code === 'auth/wrong-password' || msg.includes('invalid credential')) {
        return "That email or password doesn't look right. Please try again.";
    }
    if (code === 'auth/email-already-in-use' || msg.includes('email already in use')) {
        return "An account with this email address already exists. Please login instead.";
    }
    if (code === 'auth/weak-password' || msg.includes('weak password')) {
        return "Password is too weak. Please choose a stronger password (minimum 6 characters).";
    }
    if (code === 'auth/invalid-email' || msg.includes('invalid email')) {
        return "Please enter a valid email address.";
    }
    if (code === 'auth/operation-not-allowed') {
        return "Firebase Console Setup Required: Email/Password authentication is disabled in your Firebase project. Please enable Email/Password in Firebase Console -> Authentication -> Sign-in method.";
    }
    if (code === 'auth/unauthorized-domain') {
        return `Firebase Console Setup Required: Domain (${window.location.hostname}) is not authorized for OAuth in Firebase. Add it in Firebase Console -> Authentication -> Settings -> Authorized domains.`;
    }
    if (code === 'auth/invalid-api-key') {
        return "Firebase Config Error: Invalid API key in firebaseClient.js. Please verify your project credentials.";
    }
    if (code === 'auth/user-disabled') {
        return "This account has been disabled by an administrator.";
    }
    if (code === 'auth/popup-closed-by-user') {
        return "Sign-in popup was closed before completing authentication.";
    }
    if (code === 'auth/too-many-requests') {
        return "Access to this account has been temporarily disabled due to many failed login attempts. You can reset your password or try again later.";
    }
    if (code === 'auth/network-request-failed') {
        return "Network connection issue. Please check your internet connection and try again.";
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

// Helper to wait for Firebase to resolve initial Auth state
function getCurrentFirebaseUser() {
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
 * Checks for an active Firebase session.
 * Redirects to login.html only if no active user session exists.
 */
export async function requireAuth() {
    try {
        logAuth('Checking active session via Firebase Auth...');
        const user = await getCurrentFirebaseUser();
        
        if (!user) {
            logAuth('Redirect reason: No active Firebase user found. Redirecting to login.html');
            window.location.href = 'login.html';
            return null;
        }
        
        logAuth('Session found / restored successfully:', { uid: user.uid, email: user.email });
        
        let fullName = user.displayName || (user.email ? user.email.split('@')[0] : "User");
        let token = null;

        try {
            token = await user.getIdToken();
            const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.user?.full_name) {
                    fullName = result.user.full_name;
                }
                logAuth('Backend profile sync succeeded.');
            } else {
                logAuth(`Backend profile fetch returned HTTP ${response.status}. Using Firebase session info.`);
            }
        } catch (fetchErr) {
            logAuth('Backend profile sync offline or unreachable. Falling back to Firebase user info:', fetchErr.message);
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
        window.location.href = 'login.html';
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
 * Redirects authenticated users from auth pages (e.g. login.html) to dashboard.html.
 */

export async function redirectIfAuthenticated() {
    try {
        const user = await getCurrentFirebaseUser();
        if (user) {
            logAuth('Redirect reason: Authenticated user detected on auth page. Redirecting to dashboard.html');
            window.location.href = 'dashboard.html';
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
        window.location.href = 'login.html';
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
        return result;
    } catch (error) {
        logAuth('Google OAuth error:', error);
        throw error;
    }
}

// Setup Global Auth State Listener
onAuthStateChanged(auth, (user) => {
    logAuth(`Auth state event triggered:`, user ? user.email : 'No user');
    const path = window.location.pathname.toLowerCase();
    const isAuthPage = path.endsWith('login.html') || path.endsWith('register.html') || path.endsWith('forgot-password.html') || path.endsWith('reset-password.html');
    
    if (user) {
        logAuth('Login success: Valid Firebase session created for user:', user.email);
        if (isAuthPage) {
            logAuth('Redirect reason: Active session detected on auth page. Redirecting to dashboard.html');
            window.location.href = 'dashboard.html';
        }
    } else {
        logAuth('User signed out or no active session.');
        if (!isAuthPage && !path.endsWith('index.html') && path !== '/' && path !== '') {
            logAuth('Redirect reason: Signed out on protected page. Redirecting to login.html');
            window.location.href = 'login.html';
        }
    }
});


// -------------------------------------------------------------
// 2. Client-side Form Validation & Inputs Helpers
// -------------------------------------------------------------
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail(email) {
    if (!email) return "Email address is required.";
    if (!emailRegex.test(email)) return "Please enter a valid email address.";
    return null;
}

function validatePassword(password) {
    if (!password) return "Password is required.";
    if (password.length < 6) return "Password must be at least 6 characters long.";
    return null;
}

function setErrorState(inputEl, errorMessage) {
    const groupEl = inputEl.closest('.form-group');
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
    }
}

// -------------------------------------------------------------
// 3. Loading Spinner & Button Controls
// -------------------------------------------------------------
function setButtonLoading(buttonEl, isLoading, loadingText = "Processing...") {
    if (!buttonEl) return;
    
    if (isLoading) {
        buttonEl.disabled = true;
        buttonEl.dataset.originalText = buttonEl.innerHTML;
        buttonEl.innerHTML = `<span class="spinner" style="display: block;"></span><span>${loadingText}</span>`;
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
function showFormBanner(containerEl, message, type = 'error') {
    const existingBanner = containerEl.querySelector('.form-banner');
    if (existingBanner) existingBanner.remove();
    
    if (!message) return;
    
    const banner = document.createElement('div');
    banner.className = `form-banner form-banner--${type}`;
    
    let iconSvg = '';
    if (type === 'error') {
        iconSvg = `<svg class="form-banner-icon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        iconSvg = `<svg class="form-banner-icon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
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
function checkPasswordStrength(password) {
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
    const forgotForm = document.getElementById('forgot-form');
    const resetForm = document.getElementById('reset-form');

    // -------------------------------------------------------------
    // Login Form Handler
    // -------------------------------------------------------------
    if (loginForm) {
        redirectIfAuthenticated();
        
        const emailInput = document.getElementById('email');
        const passwordInput = document.getElementById('password');
        const submitBtn = loginForm.querySelector('button[type="submit"]');

        emailInput.addEventListener('blur', () => {
            setErrorState(emailInput, validateEmail(emailInput.value.trim()));
        });

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = emailInput.value.trim();
            const password = passwordInput.value;

            const emailErr = validateEmail(email);
            const passErr = validatePassword(password);

            setErrorState(emailInput, emailErr);
            setErrorState(passwordInput, passErr);

            if (emailErr || passErr) return;

            setButtonLoading(submitBtn, true, "Signing in...");
            showFormBanner(loginForm, null);

            try {
                logAuth('Attempting signInWithEmailAndPassword for user:', email);
                const userCredential = await signInWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;
                
                logAuth('Login success: Firebase authentication succeeded for user:', user.email);

                // Handle optional ?redirect= param
                const params = new URLSearchParams(window.location.search);
                const targetRedirect = params.get('redirect');
                let targetUrl = 'dashboard.html';
                if (targetRedirect && /^[a-zA-Z0-9_\-]+\.html$/.test(targetRedirect)) {
                    targetUrl = targetRedirect;
                } else if (targetRedirect && /^[a-zA-Z0-9_\-]+$/.test(targetRedirect)) {
                    targetUrl = `${targetRedirect}.html`;
                }

                logAuth(`Redirecting to target page: ${targetUrl}`);
                window.location.href = targetUrl;
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
    document.querySelectorAll('.btn-google-auth, #btn-google-login, #google-signin-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await signInWithGoogle();
            } catch (googleErr) {
                logAuth('Google sign-in error:', googleErr);
                const currentForm = btn.closest('form');
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
        const submitBtn = registerForm.querySelector('button[type="submit"]');

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
            const confirmErr = password === confirmPassword ? null : "Passwords do not match.";

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

                // Sync account profile with Flask backend if reachable
                try {
                    const token = await user.getIdToken();
                    const syncResponse = await fetch(`${API_BASE_URL}/api/auth/signup`, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ full_name: fullName })
                    });

                    if (!syncResponse.ok) {
                        const syncErr = await syncResponse.json().catch(() => ({}));
                        logAuth('Backend profile sync note:', syncErr);
                    }
                } catch (backendErr) {
                    logAuth('Backend sync unreachable, proceeding with Firebase authentication:', backendErr.message);
                }

                showFormBanner(registerForm, "Account created! Redirecting to dashboard...", 'success');
                registerForm.reset();
                if (strengthFill) strengthFill.className = 'password-strength-fill';
                if (strengthText) strengthText.textContent = '';
                
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 1500);

            } catch (err) {
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(registerForm, friendlyMsg, 'error');
            } finally {
                setButtonLoading(submitBtn, false);
            }
        });
    }

    // -------------------------------------------------------------
    // Forgot Password Form Handler
    // -------------------------------------------------------------
    if (forgotForm) {
        const emailInput = document.getElementById('email');
        const submitBtn = forgotForm.querySelector('button[type="submit"]');

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

            setButtonLoading(submitBtn, true, "Sending request...");
            showFormBanner(forgotForm, null);

            try {
                logAuth('Sending password reset email via Firebase to:', email);
                await sendPasswordResetEmail(auth, email);
                
                showFormBanner(forgotForm, "If an account exists for that email, we have sent a password reset link.", 'success');
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
        const passwordInput = document.getElementById('password');
        const confirmInput = document.getElementById('confirm-password');
        const submitBtn = resetForm.querySelector('button[type="submit"]');

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

        resetForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const password = passwordInput ? passwordInput.value : "";
            const confirmPassword = confirmInput ? confirmInput.value : "";

            const passErr = validatePassword(password);
            const confirmErr = password === confirmPassword ? null : "Passwords do not match.";

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
                    window.location.href = 'login.html';
                }, 2500);

            } catch (err) {
                const friendlyMsg = mapFirebaseError(err);
                showFormBanner(resetForm, friendlyMsg, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }
});