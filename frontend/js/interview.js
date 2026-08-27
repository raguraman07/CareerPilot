// CareerPilot AI — Company-Specific Interview Training Client Module (Phase 6)
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';
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
        console.error("Error retrieving auth token for interview:", err);
        return null;
    }
}

/**
 * Generate a new interview session
 */
export async function generateInterviewSession(sessionType = "MOCK_INTERVIEW", focusCategory = null, numQuestions = 10) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to start interview training.");

    const response = await fetch(`${API_BASE_URL}/api/interview/generate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            session_type: sessionType,
            focus_category: focusCategory,
            num_questions: numQuestions
        })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to initialize interview training.");
    }
    return data;
}

/**
 * Submit and evaluate a single answer
 */
export async function submitInterviewAnswer(sessionId, questionId, answerText) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to submit an answer.");

    const response = await fetch(`${API_BASE_URL}/api/interview/${sessionId}/answer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            question_id: questionId,
            answer: answerText
        })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to evaluate answer.");
    }
    return data.evaluation;
}

/**
 * Finalize session and generate report
 */
export async function finalizeInterviewSession(sessionId) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in.");

    const response = await fetch(`${API_BASE_URL}/api/interview/${sessionId}/complete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to finalize session.");
    }
    return data;
}

/**
 * Fetch interview history
 */
export async function getInterviewHistory() {
    const token = await getAuthToken();
    if (!token) return [];

    const response = await fetch(`${API_BASE_URL}/api/interview/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return [];
    return await response.json();
}

/**
 * Fetch interview readiness summary
 */
export async function getInterviewReadinessSummary() {
    const token = await getAuthToken();
    if (!token) return null;

    const response = await fetch(`${API_BASE_URL}/api/interview/readiness`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return null;
    return await response.json();
}

// -------------------------------------------------------------
// Interactive UI Handlers for interview.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const pageShell = document.getElementById('interview-page-shell');
    if (!pageShell) return;

    // Header Elements
    const roleTitleEl = document.getElementById('int-role-title');
    const companyTitleEl = document.getElementById('int-company-title');
    const readinessBadgeEl = document.getElementById('interview-readiness-badge');
    const statReadinessPctEl = document.getElementById('stat-readiness-pct');
    const statSessionsCountEl = document.getElementById('stat-sessions-count');
    const alertBox = document.getElementById('interview-alert-box');

    // Views
    const setupView = document.getElementById('interview-setup-view');
    const workspaceView = document.getElementById('interview-workspace-view');
    const reportView = document.getElementById('interview-report-view');
    const historyTableBody = document.getElementById('interview-history-table-body');

    // Setup Controls
    const modeCards = document.querySelectorAll('.mode-select-card');
    const btnStart = document.getElementById('btn-start-interview-session');

    // Workspace Elements
    const wsQCatBadge = document.getElementById('ws-q-cat-badge');
    const wsQTopicBadge = document.getElementById('ws-q-topic-badge');
    const wsQCounter = document.getElementById('ws-q-counter');
    const wsQTitle = document.getElementById('ws-q-title');
    const wsQWhy = document.getElementById('ws-q-why');
    const wsAnswerInput = document.getElementById('ws-answer-input');
    const btnWsSubmitAnswer = document.getElementById('btn-ws-submit-answer');
    const btnWsExit = document.getElementById('btn-ws-exit');

    // Feedback Elements
    const wsFeedbackCard = document.getElementById('ws-feedback-card');
    const wsFbScore = document.getElementById('ws-fb-score');
    const wsFbSummary = document.getElementById('ws-fb-summary');
    const wsFbStrengths = document.getElementById('ws-fb-strengths');
    const wsFbMissing = document.getElementById('ws-fb-missing');
    const wsFbStructure = document.getElementById('ws-fb-structure');
    const btnWsNextQ = document.getElementById('btn-ws-next-q');

    // Report Elements
    const repOverallScore = document.getElementById('rep-overall-score');
    const repReadinessBadge = document.getElementById('rep-readiness-badge');
    const repCategoryBars = document.getElementById('rep-category-bars');
    const repImprovementList = document.getElementById('rep-improvement-list');
    const btnRepRetake = document.getElementById('btn-rep-retake');

    // Local State
    let selectedMode = "MOCK_INTERVIEW";
    let activeSession = null;
    let currentQIndex = 0;

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
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // Mode Card Selection
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            modeCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedMode = card.getAttribute('data-mode') || "MOCK_INTERVIEW";
        });
    });

    // Populate History Table
    const renderHistory = async () => {
        if (!historyTableBody) return;
        try {
            const list = await getInterviewHistory();
            if (!list || list.length === 0) {
                historyTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-style: italic;">
                            No interview attempts recorded yet. Start a session above to practice!
                        </td>
                    </tr>
                `;
                return;
            }

            historyTableBody.innerHTML = '';
            list.forEach(item => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid var(--border-light)';
                
                const scoreDisplay = item.overall_score !== null ? `${item.overall_score}%` : 'In Progress';
                const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : '--';

                tr.innerHTML = `
                    <td style="padding: 0.9rem 1rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(item.session_type || 'MOCK_INTERVIEW')}</td>
                    <td style="padding: 0.9rem 1rem; color: var(--text-secondary);">${escapeHtml(item.target_role || '--')}</td>
                    <td style="padding: 0.9rem 1rem; color: var(--text-primary);">${item.answered_count || 0} / ${item.total_questions || 0}</td>
                    <td style="padding: 0.9rem 1rem; font-weight: 800; color: var(--primary);">${scoreDisplay}</td>
                    <td style="padding: 0.9rem 1rem;">
                        <span class="badge" style="background: rgba(46, 125, 50, 0.12); color: #2e7d32; font-size: 0.75rem;">
                            ${escapeHtml(item.readiness_level || 'IN_PROGRESS')}
                        </span>
                    </td>
                    <td style="padding: 0.9rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">${dateStr}</td>
                `;
                historyTableBody.appendChild(tr);
            });
        } catch (err) {
            console.error("Error loading interview history:", err);
        }
    };

    // Load Header Context & Readiness
    const loadContext = async () => {
        try {
            const goal = await getCurrentCareerGoal();
            if (goal) {
                if (roleTitleEl) roleTitleEl.textContent = goal.job_role || 'Target Role';
                if (companyTitleEl) companyTitleEl.textContent = goal.company_name || 'Target Company';
            }

            const readiness = await getInterviewReadinessSummary();
            if (readiness) {
                if (readinessBadgeEl) readinessBadgeEl.textContent = `${readiness.readiness_score}% ${readiness.readiness_level}`;
                if (statReadinessPctEl) statReadinessPctEl.textContent = `${readiness.readiness_score}%`;
                if (statSessionsCountEl) statSessionsCountEl.textContent = readiness.total_sessions || 0;
            }
        } catch (e) {
            console.error("Error initializing interview context:", e);
        }
    };

    const renderCurrentQuestion = () => {
        if (!activeSession || !activeSession.questions) return;
        const q = activeSession.questions[currentQIndex];
        if (!q) return;

        if (wsQCatBadge) wsQCatBadge.textContent = (q.category || 'technical').toUpperCase();
        if (wsQTopicBadge) wsQTopicBadge.textContent = q.topic || 'General';
        if (wsQCounter) wsQCounter.textContent = `Question ${currentQIndex + 1} of ${activeSession.questions.length}`;
        if (wsQTitle) wsQTitle.textContent = q.question || '';
        if (wsQWhy) wsQWhy.textContent = q.why_this_question || 'Relevant to role responsibilities.';
        if (wsAnswerInput) {
            wsAnswerInput.value = '';
            wsAnswerInput.disabled = false;
        }

        if (wsFeedbackCard) wsFeedbackCard.style.display = 'none';
        if (btnWsSubmitAnswer) {
            btnWsSubmitAnswer.disabled = false;
            btnWsSubmitAnswer.style.display = 'inline-flex';
        }
    };

    const handleAnswerSubmit = async () => {
        if (!activeSession) return;
        const q = activeSession.questions[currentQIndex];
        const ansText = wsAnswerInput ? wsAnswerInput.value.trim() : '';

        if (!ansText) {
            showAlert("Please provide your answer before submitting.", "danger");
            return;
        }
        hideAlert();

        if (btnWsSubmitAnswer) {
            btnWsSubmitAnswer.disabled = true;
            btnWsSubmitAnswer.classList.add('loading');
            const txt = btnWsSubmitAnswer.querySelector('.btn-text');
            if (txt) txt.textContent = "Evaluating Answer...";
        }

        try {
            const evalRes = await submitInterviewAnswer(activeSession.session_id, q.question_id, ansText);
            
            // Show Feedback Card
            if (wsFeedbackCard) wsFeedbackCard.style.display = 'block';
            if (wsFbScore) wsFbScore.textContent = `${evalRes.score || 0}/100`;
            if (wsFbSummary) wsFbSummary.textContent = evalRes.feedback || "Answer evaluated.";

            if (wsFbStrengths) {
                wsFbStrengths.innerHTML = '';
                (evalRes.strengths || []).forEach(st => {
                    const li = document.createElement('li');
                    li.textContent = st;
                    wsFbStrengths.appendChild(li);
                });
            }

            if (wsFbMissing) {
                wsFbMissing.innerHTML = '';
                (evalRes.missing_points || []).forEach(mp => {
                    const li = document.createElement('li');
                    li.textContent = mp;
                    wsFbMissing.appendChild(li);
                });
            }

            if (wsFbStructure) {
                wsFbStructure.innerHTML = '';
                (evalRes.better_answer_structure || []).forEach(step => {
                    const li = document.createElement('li');
                    li.textContent = step;
                    wsFbStructure.appendChild(li);
                });
            }

            if (btnWsSubmitAnswer) btnWsSubmitAnswer.style.display = 'none';
            if (wsAnswerInput) wsAnswerInput.disabled = true;

        } catch (err) {
            showAlert(err.message || "Failed to evaluate answer.", "danger");
            if (btnWsSubmitAnswer) {
                btnWsSubmitAnswer.disabled = false;
                btnWsSubmitAnswer.classList.remove('loading');
                const txt = btnWsSubmitAnswer.querySelector('.btn-text');
                if (txt) txt.textContent = "Submit & Evaluate Answer";
            }
        }
    };

    const handleNextQuestion = async () => {
        if (currentQIndex < activeSession.questions.length - 1) {
            currentQIndex++;
            renderCurrentQuestion();
        } else {
            // Finalize session
            try {
                if (btnWsNextQ) btnWsNextQ.disabled = true;
                const rep = await finalizeInterviewSession(activeSession.session_id);
                renderReport(rep);
            } catch (err) {
                showAlert(err.message || "Error generating report.", "danger");
            }
        }
    };

    const renderReport = (rep) => {
        if (workspaceView) workspaceView.style.display = 'none';
        if (setupView) setupView.style.display = 'none';
        if (reportView) reportView.style.display = 'block';

        if (repOverallScore) repOverallScore.textContent = `${rep.overall_score || 0}%`;
        if (repReadinessBadge) {
            repReadinessBadge.textContent = rep.readiness_level || 'READY';
        }

        if (repCategoryBars) {
            repCategoryBars.innerHTML = '';
            const breakdown = rep.performance_breakdown || {};
            for (const [cat, score] of Object.entries(breakdown)) {
                const row = document.createElement('div');
                row.innerHTML = `
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:700; color:var(--text-primary); margin-bottom:0.25rem;">
                        <span style="text-transform:capitalize;">${escapeHtml(cat.replace('_', ' '))}</span>
                        <span>${score}%</span>
                    </div>
                    <div style="width:100%; height:8px; background:rgba(168,164,146,0.2); border-radius:var(--radius-full); overflow:hidden;">
                        <div style="width:${score}%; height:100%; background:var(--primary); border-radius:var(--radius-full);"></div>
                    </div>
                `;
                repCategoryBars.appendChild(row);
            }
        }

        if (repImprovementList) {
            repImprovementList.innerHTML = '';
            (rep.personalized_improvement_plan || []).forEach(step => {
                const li = document.createElement('li');
                li.style.marginBottom = '0.35rem';
                li.textContent = step;
                repImprovementList.appendChild(li);
            });
        }

        renderHistory();
    };

    // Start Session Event
    if (btnStart) {
        btnStart.addEventListener('click', async (e) => {
            e.preventDefault();
            hideAlert();
            btnStart.disabled = true;
            btnStart.classList.add('loading');
            const txt = btnStart.querySelector('.btn-text');
            if (txt) txt.textContent = "Generating Role Questions...";

            try {
                const numQ = selectedMode === "MOCK_INTERVIEW" ? 10 : 5;
                const session = await generateInterviewSession(selectedMode, null, numQ);
                activeSession = session;
                currentQIndex = 0;

                if (setupView) setupView.style.display = 'none';
                if (reportView) reportView.style.display = 'none';
                if (workspaceView) workspaceView.style.display = 'block';

                renderCurrentQuestion();
            } catch (err) {
                showAlert(err.message || "Failed to start interview.", "danger");
            } finally {
                btnStart.disabled = false;
                btnStart.classList.remove('loading');
                const txt = btnStart.querySelector('.btn-text');
                if (txt) txt.textContent = "Start Training Session ➔";
            }
        });
    }

    if (btnWsSubmitAnswer) {
        btnWsSubmitAnswer.addEventListener('click', (e) => {
            e.preventDefault();
            handleAnswerSubmit();
        });
    }

    if (btnWsNextQ) {
        btnWsNextQ.addEventListener('click', (e) => {
            e.preventDefault();
            handleNextQuestion();
        });
    }

    if (btnWsExit) {
        btnWsExit.addEventListener('click', (e) => {
            e.preventDefault();
            if (confirm("Are you sure you want to exit the active interview training session?")) {
                if (workspaceView) workspaceView.style.display = 'none';
                if (setupView) setupView.style.display = 'block';
                renderHistory();
            }
        });
    }

    if (btnRepRetake) {
        btnRepRetake.addEventListener('click', () => {
            if (reportView) reportView.style.display = 'none';
            if (setupView) setupView.style.display = 'block';
        });
    }

    loadContext();
    renderHistory();
});

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}