import { auth } from './firebaseClient.js';
import { supabase } from './supabaseClient.js';
import { API_BASE_URL } from './config.js';

/**
 * Retrieve the active user's auth token (supports Firebase Auth & Supabase)
 */
export async function getAuthToken() {
    // 1. Try active Firebase user
    try {
        if (auth && auth.currentUser) {
            const token = await auth.currentUser.getIdToken();
            if (token) return token;
        }
    } catch (e) {
        console.warn("Firebase direct token retrieval error:", e);
    }

    // 2. Try auth.js helper
    try {
        const { getAuthToken: getFirebaseToken } = await import('./auth.js');
        const token = await getFirebaseToken();
        if (token) return token;
    } catch (e) {}

    // 3. Fallback to Supabase session
    try {
        if (supabase && supabase.auth) {
            const { data: { session } } = await supabase.auth.getSession();
            if (session?.access_token) return session.access_token;
        }
    } catch (err) {
        console.warn("Supabase token retrieval error:", err);
    }

    return null;
}

/**
 * Fetch the authenticated user's current active Career Goal.
 * Returns null if no active goal exists.
 */
export async function getCurrentCareerGoal() {
    try {
        const token = await getAuthToken();
        if (!token) return null;

        const response = await fetch(`${API_BASE_URL}/api/career-goals/current`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.warn(`Career Goal fetch returned status: ${response.status}`);
            return null;
        }

        const data = await response.json();
        return data.career_goal || null;
    } catch (err) {
        console.error("Failed to fetch current career goal:", err);
        return null;
    }
}

/**
 * Save (create or update) a Career Goal
 */
export async function saveCareerGoal(goalData, goalId = null) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to save a career goal.");
    }

    const url = goalId 
        ? `${API_BASE_URL}/api/career-goals/${goalId}`
        : `${API_BASE_URL}/api/career-goals`;
    
    const method = goalId ? 'PUT' : 'POST';

    const response = await fetch(url, {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(goalData)
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(result.error || "Failed to save career goal. Please try again.");
    }

    return result.career_goal;
}

/**
 * Global helper for future AI modules to access Career Goal Context
 */
export async function getCurrentCareerGoalContext() {
    const goal = await getCurrentCareerGoal();
    if (!goal) return null;
    return {
        goal_id: goal.id,
        company_name: goal.company_name,
        job_role: goal.job_role,
        experience_level: goal.experience_level,
        target_location: goal.target_location,
        target_timeline: goal.target_timeline,
        status: goal.status
    };
}

// -------------------------------------------------------------
// Form Handling for career-goal.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const goalForm = document.getElementById('career-goal-form');
    if (!goalForm) return;

    const companyInput = document.getElementById('company_name');
    const roleInput = document.getElementById('job_role');
    const expSelect = document.getElementById('experience_level');
    const locationInput = document.getElementById('target_location');
    const timelineSelect = document.getElementById('target_timeline');
    const submitBtn = document.getElementById('btn-save-goal');
    const alertBox = document.getElementById('goal-alert-box');
    const pageTitle = document.getElementById('goal-page-title');
    const pageSubtitle = document.getElementById('goal-page-subtitle');
    const currentGoalNotice = document.getElementById('current-goal-notice');

    let existingGoalId = null;

    const showAlert = (message, type = 'danger') => {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        if (type === 'danger') {
            alertBox.style.background = 'rgba(236, 91, 56, 0.12)';
            alertBox.style.color = '#EC5B38';
            alertBox.style.border = '1px solid rgba(236, 91, 56, 0.3)';
        } else if (type === 'success') {
            alertBox.style.background = 'rgba(46, 125, 50, 0.12)';
            alertBox.style.color = '#2e7d32';
            alertBox.style.border = '1px solid rgba(46, 125, 50, 0.3)';
        } else {
            alertBox.style.background = 'rgba(168, 164, 146, 0.15)';
            alertBox.style.color = '#524646';
            alertBox.style.border = '1px solid rgba(168, 164, 146, 0.3)';
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    const setInputError = (inputEl, errorMsg) => {
        const group = inputEl.closest('.form-group');
        if (!group) return;
        if (errorMsg) {
            group.classList.add('has-error');
            inputEl.classList.add('input-error');
            let feedback = group.querySelector('.invalid-feedback');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                group.appendChild(feedback);
            }
            feedback.textContent = errorMsg;
        } else {
            group.classList.remove('has-error');
            inputEl.classList.remove('input-error');
            const feedback = group.querySelector('.invalid-feedback');
            if (feedback) feedback.remove();
        }
    };

    // Load existing active career goal to prefill if present
    try {
        const currentGoal = await getCurrentCareerGoal();
        if (currentGoal) {
            existingGoalId = currentGoal.id;
            if (companyInput) companyInput.value = currentGoal.company_name || '';
            if (roleInput) roleInput.value = currentGoal.job_role || '';
            if (expSelect) expSelect.value = currentGoal.experience_level || '';
            if (locationInput) locationInput.value = currentGoal.target_location || '';
            if (timelineSelect) timelineSelect.value = currentGoal.target_timeline || '';

            if (pageTitle) pageTitle.textContent = "🎯 Update Your Career Goal";
            if (pageSubtitle) pageSubtitle.textContent = "Refine your target dream company and job role to tailor your AI career roadmap and interview prep.";
            if (submitBtn) {
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) btnText.textContent = "Update Career Goal";
                else submitBtn.textContent = "Update Career Goal";
            }
            if (currentGoalNotice) {
                currentGoalNotice.style.display = 'block';
                currentGoalNotice.textContent = `Current Active Goal: ${currentGoal.company_name} — ${currentGoal.job_role} (${currentGoal.experience_level})`;
            }
        }
    } catch (loadErr) {
        console.warn("Could not prefill career goal:", loadErr);
    }

    // Input blur validations
    if (companyInput) {
        companyInput.addEventListener('blur', () => {
            setInputError(companyInput, companyInput.value.trim() ? null : "Target company is required.");
        });
    }
    if (roleInput) {
        roleInput.addEventListener('blur', () => {
            setInputError(roleInput, roleInput.value.trim() ? null : "Target job role is required.");
        });
    }
    if (expSelect) {
        expSelect.addEventListener('change', () => {
            setInputError(expSelect, expSelect.value ? null : "Experience level is required.");
        });
    }

    goalForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const companyName = companyInput ? companyInput.value.trim() : '';
        const jobRole = roleInput ? roleInput.value.trim() : '';
        const expLevel = expSelect ? expSelect.value : '';
        const targetLocation = locationInput ? locationInput.value.trim() : '';
        const targetTimeline = timelineSelect ? timelineSelect.value : '';

        let hasError = false;
        if (!companyName) {
            setInputError(companyInput, "Target company is required.");
            hasError = true;
        } else {
            setInputError(companyInput, null);
        }

        if (!jobRole) {
            setInputError(roleInput, "Target job role is required.");
            hasError = true;
        } else {
            setInputError(roleInput, null);
        }

        if (!expLevel) {
            setInputError(expSelect, "Experience level is required.");
            hasError = true;
        } else {
            setInputError(expSelect, null);
        }

        if (hasError) return;

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('loading');
        }

        try {
            const payload = {
                company_name: companyName,
                job_role: jobRole,
                experience_level: expLevel,
                target_location: targetLocation,
                target_timeline: targetTimeline
            };

            await saveCareerGoal(payload, existingGoalId);

            showAlert("Career Goal saved successfully! Directing you to complete your career profile...", "success");

            setTimeout(() => {
                window.location.href = 'candidate-profile.html';
            }, 1000);

        } catch (err) {
            showAlert(err.message || "Failed to save career goal. Please try again.", "danger");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('loading');
            }
        }
    });
});
