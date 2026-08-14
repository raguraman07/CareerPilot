import { auth } from './firebaseClient.js';
import { onAuthStateChanged, signOut as firebaseSignOut } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';

// Automatically redirect 127.0.0.1 to localhost for default Firebase Auth domain authorization
if (typeof window !== 'undefined' && window.location.hostname === '127.0.0.1') {
    const normalizedUrl = new URL(window.location.href);
    normalizedUrl.hostname = 'localhost';
    window.location.replace(normalizedUrl.toString());
}

function getCurrentFirebaseUser() {
    return new Promise((resolve) => {
        const unsubscribe = onAuthStateChanged(auth, (user) => {
            unsubscribe();
            resolve(user);
        });
    });
}

// Export a compatible 'supabase' client interface mapping auth calls directly to Firebase Auth
export const supabase = {
    auth: {
        async getSession() {
            try {
                const user = await getCurrentFirebaseUser();
                if (!user) return { data: { session: null }, error: null };

                const token = await user.getIdToken();
                return {
                    data: {
                        session: {
                            access_token: token,
                            user: {
                                id: user.uid,
                                email: user.email,
                                user_metadata: { full_name: user.displayName || (user.email ? user.email.split('@')[0] : 'User') }
                            }
                        }
                    },
                    error: null
                };
            } catch (err) {
                return { data: { session: null }, error: err };
            }
        },
        async getUser() {
            try {
                const user = await getCurrentFirebaseUser();
                if (!user) return { data: { user: null }, error: null };
                return {
                    data: {
                        user: {
                            id: user.uid,
                            email: user.email,
                            user_metadata: { full_name: user.displayName || (user.email ? user.email.split('@')[0] : 'User') }
                        }
                    },
                    error: null
                };
            } catch (err) {
                return { data: { user: null }, error: err };
            }
        },
        onAuthStateChange(callback) {
            return onAuthStateChanged(auth, async (user) => {
                if (user) {
                    const token = await user.getIdToken();
                    const session = {
                        access_token: token,
                        user: {
                            id: user.uid,
                            email: user.email,
                            user_metadata: { full_name: user.displayName || (user.email ? user.email.split('@')[0] : 'User') }
                        }
                    };
                    callback('SIGNED_IN', session);
                } else {
                    callback('SIGNED_OUT', null);
                }
            });
        },
        async signOut() {
            return firebaseSignOut(auth);
        }
    }
};
