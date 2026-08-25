import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    // Form & Controls
    const resumeSelect = document.getElementById('interview-resume-select') || document.getElementById('resume-select');
    const jobmatchSelect = document.getElementById('jobmatch-select');
    const jobTitleInput = document.getElementById('interview-role-input') || document.getElementById('job-title-input');
    const jobDescInput = document.getElementById('job-desc-input');
    const interviewTypeSelect = document.getElementById('interview-type-select');
    const difficultySelect = document.getElementById('difficulty-select');
    const numQuestionsSelect = document.getElementById('num-questions-select');
    const btnGenerateInterview = document.getElementById('btn-generate-questions') || document.getElementById('btn-generate-interview');
    const genStatusMsg = document.getElementById('interview-status-msg') || document.getElementById('gen-status-msg');
    const setupForm = document.getElementById('interview-setup-form');
    const alertBox = document.getElementById('interview-alert-box');

    // Active Session Workspace
    const activeWorkspace = document.getElementById('interview-workspace') || document.getElementById('active-interview-wrapper');
    const sessTitle = document.getElementById('sess-title');
    const sessSubtitle = document.getElementById('sess-subtitle');
    const sessDiffBadge = document.getElementById('sess-diff-badge');
    const sessTypeBadge = document.getElementById('sess-type-badge');
    const sessOverallScore = document.getElementById('sess-overall-score');

    // Active Question Elements
    const qCounter = document.getElementById('q-counter');
    const qCatBadge = document.getElementById('q-cat-badge');
    const qText = document.getElementById('q-text');
    const qWhyText = document.getElementById('q-why-text');
    const qEvalText = document.getElementById('q-eval-text');
    const qGuidanceText = document.getElementById('q-guidance-text');
    const qGuidanceBox = document.getElementById('q-guidance-box');
    const btnToggleGuidance = document.getElementById('btn-toggle-guidance');
    const candidateAnswerInput = document.getElementById('candidate-answer-input');
    const btnSubmitAnswer = document.getElementById('btn-submit-answer');
    const btnPrevQ = document.getElementById('btn-prev-q');
    const btnNextQ = document.getElementById('btn-next-q');
    const btnCompleteSess = document.getElementById('btn-complete-sess');

    // Evaluation Feedback Box
    const evalFeedbackCard = document.getElementById('eval-feedback-card');
    const evalScore = document.getElementById('eval-score');
    const evalFeedbackText = document.getElementById('eval-feedback-text');
    const evalStrengthsUl = document.getElementById('eval-strengths-ul');
    const evalWeaknessesUl = document.getElementById('eval-weaknesses-ul');
    const evalImprovedGuidance = document.getElementById('eval-improved-guidance');
    const evalFollowupContainer = document.getElementById('eval-followup-container');
    const evalFollowupText = document.getElementById('eval-followup-text');

    // Overview & History
    const prepOverviewWrapper = document.getElementById('prep-overview-wrapper');
    const prepTipsUl = document.getElementById('prep-tips-ul');
    const prepWeaknessesUl = document.getElementById('prep-weaknesses-ul');
    const historyList = document.getElementById('history-list');

    // State Variables
    let currentSession = null;
    let currentQuestionIndex = 0;
    let jobMatchCache = {};

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    const showAlert = (message, isError = true) => {
        alertBox.style.display = 'block';
        if (isError) {
            alertBox.style.background = 'rgba(220, 38, 38, 0.1)';
            alertBox.style.color = '#dc2626';
            alertBox.style.border = '1px solid rgba(220, 38, 38, 0.2)';
        } else {
            alertBox.style.background = 'rgba(22, 163, 74, 0.1)';
            alertBox.style.color = '#16a34a';
            alertBox.style.border = '1px solid rgba(22, 163, 74, 0.2)';
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // 1. Populate Resumes and Job Matches
    const populateDropdowns = async () => {
        const selectContainer = document.getElementById('interview-resume-select-container');
        if (btnGenerateInterview) btnGenerateInterview.disabled = true;
        if (selectContainer) renderSelectionSkeleton(selectContainer, 1, "Loading options...");

        try {
            const token = await getAuthToken();
            if (!token) {
                renderResumeCards(selectContainer, resumeSelect, [], (selectedId) => {
                    if (btnGenerateInterview) btnGenerateInterview.disabled = !selectedId;
                });
                return;
            }

            // Resumes
            const resResp = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!resResp.ok) throw new Error("Failed to load resumes.");
            const resumes = await resResp.json();

            renderResumeCards(selectContainer, resumeSelect, resumes, (selectedId) => {
                if (btnGenerateInterview) btnGenerateInterview.disabled = !selectedId;
            });

            // Job Matches if present
            if (jobmatchSelect) {
                const jmResp = await fetch(`${API_BASE_URL}/api/job-matching/history`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (jmResp.ok) {
                    const matches = await jmResp.json();
                    jobmatchSelect.innerHTML = '<option value="" selected>-- Select a previous job match analysis --</option>';
                    if (Array.isArray(matches)) {
                        matches.forEach(m => {
                            jobMatchCache[m.id] = m;
                            const opt = document.createElement('option');
                            opt.value = m.id;
                            const scoreStr = m.match_score ? ` (${m.match_score}% Match)` : '';
                            opt.textContent = `${m.job_title || 'Position'}${scoreStr}`;
                            jobmatchSelect.appendChild(opt);
                        });
                    }
                }
            }
        } catch (err) {
            console.error("Error populating interview setup dropdowns:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", populateDropdowns);
            }
            if (btnGenerateInterview) btnGenerateInterview.disabled = true;
        }
    };

    // Auto-fill Job Description when previous job match is selected
    if (jobmatchSelect) {
        jobmatchSelect.addEventListener('change', (e) => {
            const selectedId = e.target.value;
            if (selectedId && jobMatchCache[selectedId]) {
                const m = jobMatchCache[selectedId];
                if (jobTitleInput) jobTitleInput.value = m.job_title || '';
                if (jobDescInput) jobDescInput.value = m.job_description || '';
            }
        });
    }

    // 2. Render Active Question
    const renderActiveQuestion = () => {
        if (!currentSession || !currentSession.questions || currentSession.questions.length === 0) return;

        const totalQ = currentSession.questions.length;
        const q = currentSession.questions[currentQuestionIndex];

        qCounter.textContent = `Question ${currentQuestionIndex + 1} of ${totalQ}`;
        qCatBadge.textContent = q.category || 'Technical';
        qText.textContent = q.question || 'Question';
        qWhyText.textContent = q.why_this_question || 'Assesses role fit and skills.';
        qEvalText.textContent = q.what_interviewer_is_evaluating || 'Technical understanding and communication.';
        qGuidanceText.textContent = q.answer_guidance || 'Structure your response clearly using real experience.';

        // Reset inputs & visibility
        candidateAnswerInput.value = '';
        evalFeedbackCard.style.display = 'none';
        qGuidanceBox.style.display = 'none';
        btnToggleGuidance.textContent = 'Show Guidance';

        // Check if an existing answer/evaluation exists for this question
        const answers = currentSession.answers || [];
        const existingAnswer = answers.find(a => String(a.question_id) === String(q.id));
        if (existingAnswer) {
            candidateAnswerInput.value = existingAnswer.answer || '';
            if (existingAnswer.evaluation) {
                renderAnswerEvaluation(existingAnswer.evaluation);
            }
        }

        // Navigation button states
        btnPrevQ.disabled = currentQuestionIndex === 0;
        btnNextQ.style.display = currentQuestionIndex === totalQ - 1 ? 'none' : 'inline-flex';
        btnCompleteSess.style.display = currentQuestionIndex === totalQ - 1 ? 'inline-flex' : 'none';
    };

    // 3. Render Answer Evaluation Feedback
    const renderAnswerEvaluation = (evalData) => {
        evalFeedbackCard.style.display = 'flex';
        evalScore.textContent = `${evalData.score || 0} / 100`;
        evalFeedbackText.textContent = evalData.feedback || 'Evaluation complete.';

        // Strengths
        evalStrengthsUl.innerHTML = '';
        (evalData.strengths || []).forEach(s => {
            const li = document.createElement('li');
            li.textContent = s;
            evalStrengthsUl.appendChild(li);
        });

        // Weaknesses
        evalWeaknessesUl.innerHTML = '';
        (evalData.weaknesses || []).forEach(w => {
            const li = document.createElement('li');
            li.textContent = w;
            evalWeaknessesUl.appendChild(li);
        });

        evalImprovedGuidance.textContent = evalData.improved_answer_guidance || 'N/A';

        if (evalData.follow_up_question) {
            evalFollowupContainer.style.display = 'block';
            evalFollowupText.textContent = evalData.follow_up_question;
        } else {
            evalFollowupContainer.style.display = 'none';
        }
    };

    // 4. Render Active Session Overview & Details
    const renderSessionDetails = (session) => {
        currentSession = session;
        currentQuestionIndex = 0;

        hideAlert();
        activeWorkspace.style.display = 'block';
        prepOverviewWrapper.style.display = 'block';

        sessTitle.textContent = session.job_title ? `${session.job_title} — Interview Session` : (session.interview_type ? `${session.interview_type} Interview` : 'Interview Practice Session');
        sessSubtitle.textContent = `Generated on ${session.created_at ? new Date(session.created_at).toLocaleDateString() : 'Recent'}`;
        sessDiffBadge.textContent = session.difficulty || 'Intermediate';
        sessTypeBadge.textContent = session.interview_type || 'Mixed';

        if (typeof session.overall_score === 'number') {
            sessOverallScore.style.display = 'inline-block';
            sessOverallScore.textContent = `Overall Performance: ${session.overall_score}/100`;
        } else {
            sessOverallScore.style.display = 'none';
        }

        // Overview Tips & Weaknesses
        prepTipsUl.innerHTML = '';
        (session.overall_preparation_tips || []).forEach(tip => {
            const li = document.createElement('li');
            li.textContent = tip;
            prepTipsUl.appendChild(li);
        });

        prepWeaknessesUl.innerHTML = '';
        (session.potential_weaknesses || []).forEach(w => {
            const li = document.createElement('li');
            li.textContent = w;
            prepWeaknessesUl.appendChild(li);
        });

        renderActiveQuestion();
        activeWorkspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    // Guidance Toggle
    if (btnToggleGuidance) {
        btnToggleGuidance.addEventListener('click', () => {
            if (!qGuidanceBox) return;
            const isHidden = qGuidanceBox.style.display === 'none';
            qGuidanceBox.style.display = isHidden ? 'block' : 'none';
            btnToggleGuidance.textContent = isHidden ? 'Hide Guidance' : 'Show Guidance';
        });
    }

    // Navigation Controls
    if (btnPrevQ) {
        btnPrevQ.addEventListener('click', () => {
            if (currentQuestionIndex > 0) {
                currentQuestionIndex--;
                renderActiveQuestion();
            }
        });
    }

    if (btnNextQ) {
        btnNextQ.addEventListener('click', () => {
            if (currentSession && currentQuestionIndex < currentSession.questions.length - 1) {
                currentQuestionIndex++;
                renderActiveQuestion();
            }
        });
    }

    // 5. Submit Candidate Practice Answer for Evaluation
    if (btnSubmitAnswer) {
        btnSubmitAnswer.addEventListener('click', async () => {
            if (!currentSession || !currentSession.id) return;
            const q = currentSession.questions[currentQuestionIndex];
            const answerText = candidateAnswerInput ? candidateAnswerInput.value.trim() : '';

            if (!answerText) {
                showAlert("Please type your response before submitting for evaluation.");
                return;
            }

            btnSubmitAnswer.disabled = true;
            const btnSpan = btnSubmitAnswer.querySelector('span');
            if (btnSpan) btnSpan.textContent = 'AI is evaluating your answer...';

            try {
                const token = await getAuthToken();
                const res = await fetch(`${API_BASE_URL}/api/interview/${currentSession.id}/answer`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        question_id: q.id,
                        answer: answerText
                    })
                });

                const data = await res.json();
                if (!res.ok) {
                    showAlert(data.error || "AI evaluation is temporarily unavailable. Please try again.");
                    return;
                }

                renderAnswerEvaluation(data.evaluation);

                // Update local session state
                if (!currentSession.answers) currentSession.answers = [];
                currentSession.answers = currentSession.answers.filter(a => String(a.question_id) !== String(q.id));
                currentSession.answers.push({ question_id: q.id, answer: answerText, evaluation: data.evaluation });

                if (typeof data.overall_score === 'number' && sessOverallScore) {
                    currentSession.overall_score = data.overall_score;
                    sessOverallScore.style.display = 'inline-block';
                    sessOverallScore.textContent = `Overall Performance: ${data.overall_score}/100`;
                }

            } catch (err) {
                console.error("Answer evaluation error:", err);
                showAlert("AI interview preparation is temporarily unavailable. Please try again.");
            } finally {
                btnSubmitAnswer.disabled = false;
                if (btnSpan) btnSpan.textContent = 'Submit Practice Answer';
            }
        });
    }

    // 6. Complete Session
    if (btnCompleteSess) {
        btnCompleteSess.addEventListener('click', async () => {
            if (!currentSession || !currentSession.id) return;
            try {
                const token = await getAuthToken();
                const res = await fetch(`${API_BASE_URL}/api/interview/${currentSession.id}/complete`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    showAlert(`Session completed! Final Performance Score: ${data.overall_score}/100`, false);
                    loadHistory();
                }
            } catch (err) {
                console.error("Complete session error:", err);
            }
        });
    }

    // 7. Load Session History
    const loadHistory = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/interview/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const history = await res.json();

            historyList.innerHTML = '';
            if (!Array.isArray(history) || history.length === 0) {
                historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">No previous interview sessions found.</p>';
                return;
            }

            history.forEach(item => {
                const card = document.createElement('div');
                card.className = 'history-card';

                const title = item.job_title || `${item.interview_type || 'Mixed'} Interview`;
                const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent';
                const scoreStr = typeof item.overall_score === 'number' ? ` &bull; Score: ${item.overall_score}/100` : '';

                card.innerHTML = `
                    <div>
                        <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
                            <h4 style="font-size:1rem; font-weight:600; color:var(--text-color);">${title}</h4>
                            <span class="q-badge" style="margin:0; padding:0.15rem 0.5rem; font-size:0.75rem;">${item.difficulty || 'Intermediate'}</span>
                        </div>
                        <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0.25rem;">${item.num_questions || 10} Questions &bull; Created on ${dateStr}${scoreStr}</p>
                    </div>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-secondary btn-view-session" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem;">View</button>
                        <button class="btn btn-secondary btn-delete-session" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem; color:var(--error-color); border-color:rgba(220,38,38,0.3);">Delete</button>
                    </div>
                `;
                historyList.appendChild(card);
            });

            // View event handlers
            historyList.querySelectorAll('.btn-view-session').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const sessId = e.currentTarget.getAttribute('data-id');
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/interview/${sessId}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to load interview session.");
                        const record = await resp.json();
                        renderSessionDetails(record);
                    } catch (err) {
                        showAlert("Failed to load selected interview session.");
                    }
                });
            });

            // Delete event handlers
            historyList.querySelectorAll('.btn-delete-session').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const sessId = e.currentTarget.getAttribute('data-id');
                    if (!confirm("Are you sure you want to delete this interview preparation session?")) return;
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/interview/${sessId}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to delete interview session.");
                        loadHistory();
                    } catch (err) {
                        showAlert("Failed to delete selected interview session.");
                    }
                });
            });

        } catch (err) {
            console.error("History load error:", err);
            historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">Unable to load interview session history.</p>';
        }
    };

    // 8. Generate New Interview Session Form Submit
    setupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const resumeId = resumeSelect.value;
        const jobMatchId = jobmatchSelect.value;
        const jobTitle = jobTitleInput.value.trim();
        const jobDesc = jobDescInput.value.trim();
        const interviewType = interviewTypeSelect.value;
        const difficulty = difficultySelect.value;
        const numQuestions = parseInt(numQuestionsSelect.value, 10) || 10;

        if (!resumeId) {
            showAlert("Please select an uploaded resume.");
            return;
        }

        btnGenerateInterview.disabled = true;
        btnGenerateInterview.querySelector('span').textContent = 'Gemini is preparing a personalized interview...';
        genStatusMsg.style.display = 'inline';
        genStatusMsg.textContent = 'Analyzing resume and job requirements to build customized questions...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/interview/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    resume_id: resumeId,
                    job_match_id: jobMatchId || undefined,
                    job_title: jobTitle,
                    job_description: jobDesc,
                    interview_type: interviewType,
                    difficulty: difficulty,
                    num_questions: numQuestions
                })
            });

            const data = await res.json();
            if (!res.ok) {
                showAlert(data.error || "AI interview preparation is temporarily unavailable. Please try again.");
                return;
            }

            const record = data.session || data;
            renderSessionDetails(record);
            showAlert("Personalized AI interview preparation session generated!", false);
            loadHistory();

        } catch (err) {
            console.error("Interview generation error:", err);
            showAlert("AI interview preparation is temporarily unavailable. Please try again.");
        } finally {
            btnGenerateInterview.disabled = false;
            btnGenerateInterview.querySelector('span').textContent = 'Generate Interview Session';
            genStatusMsg.style.display = 'none';
        }
    });

    // Initial load
    populateDropdowns();
    loadHistory();
});