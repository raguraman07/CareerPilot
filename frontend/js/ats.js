import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunAts = document.getElementById('btn-run-ats');
    const form = document.getElementById('ats-setup-form') || document.getElementById('ats-grader-form');
    const resultsWrapper = document.getElementById('ats-results-wrapper');
    const alertBox = document.getElementById('ats-alert-box');
    const statusMsg = document.getElementById('ats-status-msg');

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
        } else if (type === 'success') {
            alertBox.style.background = 'rgba(56, 142, 60, 0.15)';
            alertBox.style.color = '#81c784';
            alertBox.style.border = '1px solid rgba(56, 142, 60, 0.3)';
        } else {
            alertBox.style.background = 'rgba(99, 102, 241, 0.15)';
            alertBox.style.color = '#818cf8';
            alertBox.style.border = '1px solid rgba(99, 102, 241, 0.3)';
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    const loadResumes = async () => {
        const selectContainer = document.getElementById('resume-select-container');
        if (btnRunAts) btnRunAts.disabled = true;
        if (selectContainer) renderSelectionSkeleton(selectContainer, 1, "Loading options...");

        try {
            const token = await getAuthToken();
            if (!token) {
                renderResumeCards(selectContainer, resumeSelect, [], (selectedId) => {
                    if (btnRunAts) btnRunAts.disabled = !selectedId;
                });
                return;
            }

            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to load resume list.");
            const data = await res.json();

            renderResumeCards(selectContainer, resumeSelect, data, (selectedId) => {
                if (btnRunAts) btnRunAts.disabled = !selectedId;
            });

        } catch (err) {
            console.error("ATS resume load error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", loadResumes);
            }
            if (btnRunAts) btnRunAts.disabled = true;
        }
    };

    const renderBadges = (containerId, items, typeClass) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<span style="font-size:0.85rem; color:var(--text-muted);">None detected</span>';
            return;
        }
        items.forEach(item => {
            const span = document.createElement('span');
            span.className = `badge badge--${typeClass}`;
            span.textContent = item;
            container.appendChild(span);
        });
    };

    const renderAtsDetails = (payload) => {
        hideAlert();
        if (resultsWrapper) resultsWrapper.style.display = 'grid';

        const data = payload.ats_result || payload;
        const results = data.ats_results || {};

        const score = typeof data.overall_score === 'number' ? data.overall_score : 80;
        const scoreLevel = data.score_level || (score >= 90 ? "Excellent ATS Fit" : (score >= 75 ? "Strong ATS Fit" : "Needs Improvement"));

        // Render main score
        const scoreEl = document.getElementById('res-ats-score') || document.getElementById('overall-val');
        if (scoreEl) scoreEl.textContent = `${score}%`;

        const badgeEl = document.getElementById('res-ats-badge') || document.getElementById('score-level-badge');
        if (badgeEl) badgeEl.textContent = scoreLevel;

        const summaryEl = document.getElementById('res-ats-summary');
        if (summaryEl) summaryEl.textContent = `Your resume scored ${score}% for ATS machine-readability.`;

        // Render keywords
        const kwAnalysis = results.keyword_analysis || {};
        renderBadges('res-keywords-found', kwAnalysis.found_keywords || results.found_keywords || [], 'technical');
        renderBadges('found-keywords-badges', kwAnalysis.found_keywords || [], 'technical');

        renderBadges('res-keywords-missing', kwAnalysis.missing_keywords || results.missing_keywords || [], 'missing');
        renderBadges('missing-keywords-badges', kwAnalysis.missing_keywords || [], 'missing');

        // Render Warnings
        const warningsList = document.getElementById('res-ats-warnings') || document.getElementById('ats-warnings-list');
        const warnings = results.ats_warnings || data.ats_warnings || [];
        if (warningsList) {
            warningsList.innerHTML = '';
            if (warnings.length > 0) {
                warnings.forEach(w => {
                    const li = document.createElement('li');
                    li.className = 'analysis-list-item weakness-item';
                    li.textContent = w;
                    warningsList.appendChild(li);
                });
            } else {
                warningsList.innerHTML = '<li style="color: var(--text-muted); list-style: none;">No ATS parsing warnings detected!</li>';
            }
        }

        // Render Recommendations
        const recsList = document.getElementById('res-ats-recommendations') || document.getElementById('ats-recs-list');
        const recs = results.overall_recommendations || data.recommendations || [];
        if (recsList) {
            recsList.innerHTML = '';
            if (recs.length > 0) {
                recs.forEach((rec, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${rec}</div>`;
                    recsList.appendChild(li);
                });
            } else {
                recsList.innerHTML = '<li style="color: var(--text-muted); list-style: none;">No urgent adjustments needed.</li>';
            }
        }
    };

    const loadLatestScore = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/ats/latest`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data && (data.overall_score || data.ats_result)) {
                    renderAtsDetails(data);
                }
            }
        } catch (e) {
            // Ignore error if no past evaluation exists
        }
    };

    const runAtsAudit = async (resumeId) => {
        if (!resumeId) {
            showAlert("Please select a valid resume to analyze.", 'warning');
            return;
        }

        if (btnRunAts) btnRunAts.disabled = true;
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'Running ATS scan...';
        }

        try {
            const token = await getAuthToken();
            
            const res = await fetch(`${API_BASE_URL}/api/ats/analyze/${resumeId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ resume_id: resumeId })
            });

            const data = await res.json();

            if (!res.ok || !data.success) {
                const errMsg = data.error || data.message || "Failed to analyze resume for ATS compliance.";
                throw new Error(errMsg);
            }

            if (statusMsg) statusMsg.style.display = 'none';
            renderAtsDetails(data);
            showAlert("ATS analysis completed successfully.", 'success');
        } catch (err) {
            if (statusMsg) statusMsg.style.display = 'none';
            showAlert(err.message || "An unexpected error occurred during ATS analysis.", 'danger');
        } finally {
            if (btnRunAts) btnRunAts.disabled = false;
        }
    };

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const resumeId = resumeSelect ? resumeSelect.value : null;
            runAtsAudit(resumeId);
        });
    }

    if (btnRunAts) {
        btnRunAts.addEventListener('click', (e) => {
            const resumeId = resumeSelect ? resumeSelect.value : null;
            if (resumeId) runAtsAudit(resumeId);
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            loadResumes().then(loadLatestScore);
        }

        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                loadResumes().then(loadLatestScore);
            }
        });
    };

    init();
});