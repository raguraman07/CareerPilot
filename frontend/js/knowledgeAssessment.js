// CareerPilot AI — Knowledge Assessment & Skill Verification Client Module (Phase 5)
import { supabase } from './supabaseClient.js';
import { API_BASE_URL } from './config.js';

/**
 * Retrieve active user auth token
 */
export async function getAuthToken() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    } catch (err) {
        console.error("Error retrieving auth token for knowledge assessment:", err);
        return null;
    }
}

/**
 * Generate a new assessment session for a specific skill
 */
export async function generateSkillAssessment(skillId, skillName) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to start an assessment.");
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/skill-assessment/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                skill_id: skillId,
                skill_name: skillName
            })
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || "Failed to initialize skill assessment session.");
        }

        return data;
    } catch (err) {
        if (err.name === 'TypeError' && err.message.includes('fetch')) {
            throw new Error("Unable to connect to the AI server. The backend may be waking up—please wait 10 seconds and try again.");
        }
        throw err;
    }
}

/**
 * Retrieve an existing assessment session
 */
export async function getAssessmentSession(assessmentId) {
    const token = await getAuthToken();
    if (!token) return null;

    const response = await fetch(`${API_BASE_URL}/api/skill-assessment/${assessmentId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return null;
    return await response.json();
}

/**
 * Submit candidate answers for evaluation
 */
export async function submitAssessmentSession(assessmentId, answers) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to submit an assessment.");
    }

    const response = await fetch(`${API_BASE_URL}/api/skill-assessment/${assessmentId}/submit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ answers })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to submit assessment.");
    }

    return data;
}

/**
 * Retrieve full result and review for an assessment
 */
export async function getAssessmentResult(assessmentId) {
    const token = await getAuthToken();
    if (!token) return null;

    const response = await fetch(`${API_BASE_URL}/api/skill-assessment/${assessmentId}/result`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return null;
    return await response.json();
}

/**
 * Retrieve assessment history
 */
export async function getAssessmentHistory(skillName = null) {
    const token = await getAuthToken();
    if (!token) return [];

    let url = `${API_BASE_URL}/api/skill-assessment/history`;
    if (skillName) url += `?skill_name=${encodeURIComponent(skillName)}`;

    const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return [];
    const data = await response.json();
    return data.history || [];
}

// -------------------------------------------------------------
// Interactive UI Handlers for knowledge-assessment.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const testPage = document.getElementById('knowledge-assessment-page');
    if (!testPage) return;

    // Read URL query params
    const urlParams = new URLSearchParams(window.location.search);
    const skillId = urlParams.get('skill_id');
    const skillName = urlParams.get('skill_name') || 'Skill';
    const existingAssessId = urlParams.get('assessment_id');

    // DOM Elements
    const skillNameEl = document.getElementById('test-skill-name');
    const roleContextEl = document.getElementById('test-role-context');
    const difficultyBadgeEl = document.getElementById('test-difficulty-badge');
    const timerDisplayEl = document.getElementById('test-timer-display');
    const questionCounterEl = document.getElementById('test-question-counter');
    const progressBarEl = document.getElementById('test-progress-bar');
    
    const questionBoxEl = document.getElementById('test-question-box');
    const qTypeBadgeEl = document.getElementById('test-qtype-badge');
    const qTopicBadgeEl = document.getElementById('test-qtopic-badge');
    const qTitleEl = document.getElementById('test-qtitle');
    const qOptionsContainerEl = document.getElementById('test-options-container');
    
    const btnPrev = document.getElementById('btn-test-prev');
    const btnNext = document.getElementById('btn-test-next');
    const btnSubmit = document.getElementById('btn-test-submit');
    const alertBox = document.getElementById('test-alert-box');

    let currentAssessment = null;
    let questions = [];
    let currentIndex = 0;
    const userAnswers = {};
    let timerInterval = null;
    let secondsRemaining = 15 * 60;

    const showAlert = (message, type = 'danger', showRetry = false, onRetry = null) => {
        if (!alertBox) return;
        alertBox.style.display = 'flex';
        alertBox.style.justifyContent = 'space-between';
        alertBox.style.alignItems = 'center';
        alertBox.style.flexWrap = 'wrap';
        alertBox.style.gap = '0.75rem';
        if (type === 'danger') {
            alertBox.style.background = 'rgba(236, 91, 56, 0.12)';
            alertBox.style.color = '#EC5B38';
            alertBox.style.border = '1px solid rgba(236, 91, 56, 0.3)';
        } else if (type === 'info') {
            alertBox.style.background = 'rgba(82, 70, 70, 0.08)';
            alertBox.style.color = 'var(--text-primary)';
            alertBox.style.border = '1px solid var(--border)';
        } else if (type === 'success') {
            alertBox.style.background = 'rgba(46, 125, 50, 0.12)';
            alertBox.style.color = '#2e7d32';
            alertBox.style.border = '1px solid rgba(46, 125, 50, 0.3)';
        }

        alertBox.innerHTML = `<span>${message}</span>`;
        if (showRetry && onRetry) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn btn-primary btn-sm';
            retryBtn.style.padding = '0.4rem 1rem';
            retryBtn.style.fontSize = '0.82rem';
            retryBtn.textContent = 'Retry Now ➔';
            retryBtn.addEventListener('click', (e) => {
                e.preventDefault();
                onRetry();
            });
            alertBox.appendChild(retryBtn);
        }
    };

    const hideAlert = () => {
        if (alertBox) alertBox.style.display = 'none';
    };

    const startTimer = (minutes) => {
        secondsRemaining = minutes * 60;
        clearInterval(timerInterval);
        
        const updateTimerDisplay = () => {
            const m = Math.floor(secondsRemaining / 60);
            const s = secondsRemaining % 60;
            if (timerDisplayEl) {
                timerDisplayEl.textContent = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
                if (secondsRemaining < 120) {
                    timerDisplayEl.style.color = 'var(--danger)';
                    timerDisplayEl.style.borderColor = 'var(--danger)';
                }
            }
            if (secondsRemaining <= 0) {
                clearInterval(timerInterval);
                showAlert("Time expired! Automatically submitting your answers...", "danger");
                handleSubmit();
            }
            secondsRemaining--;
        };

        updateTimerDisplay();
        timerInterval = setInterval(updateTimerDisplay, 1000);
    };

    const renderCurrentQuestion = () => {
        if (!questions || questions.length === 0) return;
        const q = questions[currentIndex];

        // Header & Counters
        if (questionCounterEl) questionCounterEl.textContent = `Question ${currentIndex + 1} of ${questions.length}`;
        const pct = Math.round(((currentIndex + 1) / questions.length) * 100);
        if (progressBarEl) progressBarEl.style.width = `${pct}%`;

        if (qTypeBadgeEl) {
            let typeLabel = "Multiple Choice";
            if (q.type === 'true_false') typeLabel = "True / False";
            else if (q.type === 'scenario') typeLabel = "Scenario Question";
            else if (q.type === 'short_answer') typeLabel = "Short Answer";
            qTypeBadgeEl.textContent = typeLabel;
        }

        if (qTopicBadgeEl) {
            qTopicBadgeEl.textContent = q.topic || "General";
        }

        if (qTitleEl) {
            qTitleEl.textContent = q.question || "";
        }

        // Render Options / Inputs
        if (qOptionsContainerEl) {
            qOptionsContainerEl.innerHTML = '';
            const currentSavedAnswer = userAnswers[q.id] || "";

            if (q.type === 'mcq' || q.type === 'scenario') {
                const list = document.createElement('div');
                list.style.cssText = 'display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1rem;';

                (q.options || []).forEach((opt, optIdx) => {
                    const label = document.createElement('label');
                    const isChecked = currentSavedAnswer === opt;
                    label.style.cssText = `display: flex; align-items: center; gap: 0.75rem; padding: 1rem 1.25rem; background: ${isChecked ? 'rgba(236, 91, 56, 0.08)' : 'var(--surface)'}; border: 2px solid ${isChecked ? 'var(--primary)' : 'var(--border-light)'}; border-radius: var(--radius-md); cursor: pointer; transition: all var(--transition-fast);`;

                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = `option-${q.id}`;
                    radio.value = opt;
                    radio.checked = isChecked;
                    radio.style.accentColor = 'var(--primary)';

                    radio.addEventListener('change', () => {
                        userAnswers[q.id] = opt;
                        renderCurrentQuestion();
                    });

                    const span = document.createElement('span');
                    span.style.cssText = 'font-size: 0.95rem; color: var(--text-primary); font-weight: 500;';
                    span.textContent = opt;

                    label.appendChild(radio);
                    label.appendChild(span);
                    list.appendChild(label);
                });
                qOptionsContainerEl.appendChild(list);

            } else if (q.type === 'true_false') {
                const tfContainer = document.createElement('div');
                tfContainer.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;';

                ["True", "False"].forEach(tfOpt => {
                    const isChecked = currentSavedAnswer.toLowerCase() === tfOpt.toLowerCase();
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.style.cssText = `padding: 1.25rem; font-size: 1.1rem; font-weight: 700; border-radius: var(--radius-md); border: 2px solid ${isChecked ? 'var(--primary)' : 'var(--border-light)'}; background: ${isChecked ? 'var(--primary)' : 'var(--surface)'}; color: ${isChecked ? '#FFFFFF' : 'var(--text-primary)'}; cursor: pointer; transition: all var(--transition-fast);`;
                    btn.textContent = tfOpt;

                    btn.addEventListener('click', () => {
                        userAnswers[q.id] = tfOpt;
                        renderCurrentQuestion();
                    });

                    tfContainer.appendChild(btn);
                });
                qOptionsContainerEl.appendChild(tfContainer);

            } else if (q.type === 'short_answer') {
                const shortDiv = document.createElement('div');
                shortDiv.style.cssText = 'margin-top: 1rem;';

                const textarea = document.createElement('textarea');
                textarea.rows = 5;
                textarea.placeholder = "Write your conceptual explanation here (2-4 clear sentences)...";
                textarea.style.cssText = 'width: 100%; padding: 1rem; border: 1.5px solid var(--border); border-radius: var(--radius-md); font-family: inherit; font-size: 0.95rem; color: var(--text-primary); background: var(--surface); resize: vertical; line-height: 1.5;';
                textarea.value = currentSavedAnswer;

                textarea.addEventListener('input', (e) => {
                    userAnswers[q.id] = e.target.value;
                });

                shortDiv.appendChild(textarea);
                qOptionsContainerEl.appendChild(shortDiv);
            }
        }

        // Navigation state
        if (btnPrev) btnPrev.disabled = currentIndex === 0;
        if (btnNext) btnNext.style.display = currentIndex === questions.length - 1 ? 'none' : 'inline-flex';
        if (btnSubmit) btnSubmit.style.display = currentIndex === questions.length - 1 ? 'inline-flex' : 'none';
    };

    const handleSubmit = async () => {
        if (!currentAssessment) return;
        
        // Check if unanswered questions exist
        const answeredCount = Object.keys(userAnswers).length;
        if (answeredCount < questions.length) {
            const proceed = confirm(`You have answered ${answeredCount} of ${questions.length} questions. Submit anyway?`);
            if (!proceed) return;
        }

        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.classList.add('loading');
            const txt = btnSubmit.querySelector('.btn-text');
            if (txt) txt.textContent = "Evaluating answers...";
        }

        try {
            clearInterval(timerInterval);
            const result = await submitAssessmentSession(currentAssessment.assessment_id, userAnswers);
            window.location.href = `assessment-result.html?assessment_id=${result.assessment_id}`;
        } catch (err) {
            showAlert(err.message || "Failed to evaluate assessment.", "danger");
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.classList.remove('loading');
                const txt = btnSubmit.querySelector('.btn-text');
                if (txt) txt.textContent = "Submit Assessment";
            }
        }
    };

    // Initialize Assessment Session with Auto-Retry
    const loadAssessmentSession = async (attempt = 1) => {
        hideAlert();
        if (qTitleEl) qTitleEl.textContent = "Connecting to CareerPilot AI and preparing your assessment questions...";

        try {
            let sessionData = null;
            if (existingAssessId) {
                sessionData = await getAssessmentSession(existingAssessId);
            } else if (skillId || skillName) {
                sessionData = await generateSkillAssessment(skillId, skillName);
            }

            if (!sessionData || !sessionData.questions || sessionData.questions.length === 0) {
                showAlert("Could not generate assessment questions. Please try again.", "danger", true, () => loadAssessmentSession(1));
                if (qTitleEl) qTitleEl.textContent = "Assessment generation incomplete.";
                return;
            }

            currentAssessment = sessionData;
            questions = sessionData.questions;

            if (skillNameEl) skillNameEl.textContent = sessionData.skill_name || skillName;
            if (roleContextEl) roleContextEl.textContent = `${sessionData.target_role || 'Target Role'} at ${sessionData.target_company || 'Company'}`;
            if (difficultyBadgeEl) difficultyBadgeEl.textContent = sessionData.difficulty || 'MEDIUM';

            startTimer(sessionData.time_limit_minutes || 15);
            renderCurrentQuestion();

        } catch (loadErr) {
            console.error(`Assessment load error (attempt ${attempt}):`, loadErr);
            if (attempt < 3 && (loadErr.message.includes('waking up') || loadErr.message.includes('fetch') || loadErr.message.includes('connect'))) {
                showAlert(`Connecting to AI backend... (Attempt ${attempt}/3)`, "info");
                setTimeout(() => loadAssessmentSession(attempt + 1), 3000);
            } else {
                showAlert(loadErr.message || "Failed to initialize assessment.", "danger", true, () => loadAssessmentSession(1));
                if (qTitleEl) qTitleEl.textContent = "Could not load question. Please click Retry Now above.";
            }
        }
    };

    loadAssessmentSession(1);

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentIndex > 0) {
                currentIndex--;
                renderCurrentQuestion();
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentIndex < questions.length - 1) {
                currentIndex++;
                renderCurrentQuestion();
            }
        });
    }

    if (btnSubmit) {
        btnSubmit.addEventListener('click', (e) => {
            e.preventDefault();
            handleSubmit();
        });
    }
});
