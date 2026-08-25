import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    // Form & Controls
    const resumeSelect = document.getElementById('interview-resume-select') || document.getElementById('resume-select');
    const jobTitleInput = document.getElementById('interview-role-input') || document.getElementById('job-title-input');
    const btnGenerateInterview = document.getElementById('btn-generate-questions') || document.getElementById('btn-generate-interview');
    const statusMsg = document.getElementById('interview-status-msg') || document.getElementById('gen-status-msg');
    const setupForm = document.getElementById('interview-setup-form');
    const alertBox = document.getElementById('interview-alert-box');

    // Active Workspace Elements
    const activeWorkspace = document.getElementById('interview-workspace') || document.getElementById('active-interview-wrapper');
    const qCatBadge = document.getElementById('q-category-badge') || document.getElementById('q-cat-badge');
    const qDiffBadge = document.getElementById('q-difficulty-badge') || document.getElementById('sess-diff-badge');
    const qProgressText = document.getElementById('q-progress-text') || document.getElementById('q-counter');
    const qTitleText = document.getElementById('q-title-text') || document.getElementById('q-text');
    const qGuidanceText = document.getElementById('q-guidance-text');
    const answerForm = document.getElementById('answer-form');
    const answerTextarea = document.getElementById('answer-textarea') || document.getElementById('candidate-answer-input');
    const btnSubmitAnswer = document.getElementById('btn-submit-answer');
    const btnNextQuestion = document.getElementById('btn-next-question');

    // Feedback Card Elements
    const feedbackCard = document.getElementById('answer-feedback-card') || document.getElementById('eval-feedback-card');
    const feedbackScore = document.getElementById('feedback-score-val') || document.getElementById('eval-score');
    const feedbackStrengths = document.getElementById('feedback-strengths') || document.getElementById('eval-strengths-ul');
    const feedbackImprovements = document.getElementById('feedback-improvements') || document.getElementById('eval-weaknesses-ul');
    const feedbackModelAnswer = document.getElementById('feedback-model-answer') || document.getElementById('eval-improved-guidance');

    // State Variables
    let currentSession = null;
    let currentQuestionIndex = 0;

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    const showAlert = (message, type = 'danger') => {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        if (type === 'danger') {
            alertBox.style.background = 'rgba(211, 47, 47, 0.15)';
            alertBox.style.color = '#e57373';
            alertBox.style.border = '1px solid rgba(211, 47, 47, 0.3)';
        } else {
            alertBox.style.background = 'rgba(56, 142, 60, 0.15)';
            alertBox.style.color = '#81c784';
            alertBox.style.border = '1px solid rgba(56, 142, 60, 0.3)';
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // Populate Resumes Dropdown
    const populateResumes = async () => {
        const selectContainer = document.getElementById('interview-resume-select-container') || document.getElementById('resume-select-container');
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

            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to load resumes.");
            const data = await res.json();

            renderResumeCards(selectContainer, resumeSelect, data, (selectedId) => {
                if (btnGenerateInterview) btnGenerateInterview.disabled = !selectedId;
            });

        } catch (err) {
            console.error("Resume dropdown error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", populateResumes);
            }
            if (btnGenerateInterview) btnGenerateInterview.disabled = true;
        }
    };

    const renderActiveQuestion = () => {
        if (!currentSession || !currentSession.questions || currentSession.questions.length === 0) return;

        const total = currentSession.questions.length;
        const q = currentSession.questions[currentQuestionIndex];

        if (qProgressText) qProgressText.textContent = `Question ${currentQuestionIndex + 1} of ${total}`;
        if (qCatBadge) qCatBadge.textContent = q.category || 'Technical';
        if (qDiffBadge) qDiffBadge.textContent = currentSession.difficulty || 'Medium';
        if (qTitleText) qTitleText.textContent = q.question || q.question_text || 'Interview question';
        if (qGuidanceText) qGuidanceText.textContent = q.answering_guidance || q.answer_guidance || 'Structure response using STAR method (Situation, Task, Action, Result).';

        if (answerTextarea) answerTextarea.value = '';
        if (feedbackCard) feedbackCard.style.display = 'none';

        if (btnNextQuestion) {
            btnNextQuestion.style.display = currentQuestionIndex < total - 1 ? 'inline-flex' : 'none';
        }
    };

    const renderFeedback = (feedback) => {
        if (!feedbackCard) return;
        feedbackCard.style.display = 'block';

        const score = typeof feedback.score === 'number' ? feedback.score : 85;
        if (feedbackScore) feedbackScore.textContent = `${score} / 100`;

        if (feedbackStrengths) {
            feedbackStrengths.innerHTML = '';
            (feedback.strengths || []).forEach(s => {
                const li = document.createElement('li');
                li.className = 'analysis-list-item strength-item';
                li.textContent = s;
                feedbackStrengths.appendChild(li);
            });
        }

        if (feedbackImprovements) {
            feedbackImprovements.innerHTML = '';
            (feedback.weaknesses || feedback.improvements || []).forEach(w => {
                const li = document.createElement('li');
                li.className = 'analysis-list-item weakness-item';
                li.textContent = w;
                feedbackImprovements.appendChild(li);
            });
        }

        if (feedbackModelAnswer) {
            feedbackModelAnswer.textContent = feedback.improved_answer_guidance || feedback.model_answer || feedback.feedback || 'Answer structured clearly.';
        }
    };

    const generateQuestions = async () => {
        const resumeId = resumeSelect ? resumeSelect.value : null;
        const targetRole = jobTitleInput ? jobTitleInput.value.trim() : 'Software Engineer';

        if (!resumeId) {
            showAlert("Please select a resume.", 'danger');
            return;
        }

        if (btnGenerateInterview) btnGenerateInterview.disabled = true;
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'Generating custom interview questions...';
        }

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
                    job_title: targetRole,
                    num_questions: 5
                })
            });

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to generate interview session.");
            }

            currentSession = data.session || data;
            currentQuestionIndex = 0;

            if (statusMsg) statusMsg.style.display = 'none';
            if (activeWorkspace) activeWorkspace.style.display = 'flex';
            renderActiveQuestion();
            showAlert("Interview session generated successfully.", 'success');

        } catch (err) {
            if (statusMsg) statusMsg.style.display = 'none';
            showAlert(err.message || "An error occurred generating interview questions.", 'danger');
        } finally {
            if (btnGenerateInterview) btnGenerateInterview.disabled = false;
        }
    };

    const submitAnswer = async () => {
        if (!currentSession || !currentSession.questions) return;
        const q = currentSession.questions[currentQuestionIndex];
        const answerText = answerTextarea ? answerTextarea.value.trim() : '';

        if (!answerText) {
            showAlert("Please type an answer before submitting.", 'danger');
            return;
        }

        try {
            const token = await getAuthToken();

            const res = await fetch(`${API_BASE_URL}/api/interview/evaluate-answer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    question_text: q.question || q.question_text,
                    candidate_answer: answerText,
                    session_id: currentSession.id
                })
            });

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to evaluate answer.");
            }

            renderFeedback(data.evaluation || data);
            showAlert("Answer evaluated successfully.", 'success');

        } catch (err) {
            showAlert(err.message || "Failed to evaluate answer.", 'danger');
        }
    };

    if (setupForm) {
        setupForm.addEventListener('submit', (e) => {
            e.preventDefault();
            generateQuestions();
        });
    }

    if (btnGenerateInterview) {
        btnGenerateInterview.addEventListener('click', (e) => {
            generateQuestions();
        });
    }

    if (answerForm) {
        answerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            submitAnswer();
        });
    }

    if (btnSubmitAnswer) {
        btnSubmitAnswer.addEventListener('click', (e) => {
            submitAnswer();
        });
    }

    if (btnNextQuestion) {
        btnNextQuestion.addEventListener('click', () => {
            if (currentSession && currentQuestionIndex < currentSession.questions.length - 1) {
                currentQuestionIndex++;
                renderActiveQuestion();
            }
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            populateResumes();
        }

        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                populateResumes();
            }
        });
    };

    init();
});