import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunAts = document.getElementById('btn-run-ats');
    const btnText = document.getElementById('btn-text');
    const spinner = document.getElementById('ats-spinner');
    const form = document.getElementById('ats-grader-form');
    const resultsWrapper = document.getElementById('ats-results-wrapper');
    const alertBox = document.getElementById('ats-alert-box');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No user is logged in.");
        return session.access_token;
    };

    const showAlert = (message, type = 'danger') => {
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
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    const populateDropdown = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to load resume list.");
            const data = await res.json();

            resumeSelect.innerHTML = '<option value="" disabled selected>-- Select an Uploaded Resume --</option>';
            if (!data || data.length === 0) {
                resumeSelect.innerHTML = '<option value="" disabled>No resumes found. Please upload a resume first.</option>';
                btnRunAts.disabled = true;
                return;
            }

            data.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.id;
                const uploadDate = item.uploaded_at ? new Date(item.uploaded_at).toLocaleDateString() : '';
                opt.textContent = `${item.filename} ${uploadDate ? `(${uploadDate})` : ''}`;
                resumeSelect.appendChild(opt);
            });
            btnRunAts.disabled = false;
        } catch (err) {
            resumeSelect.innerHTML = '<option value="" disabled>Error loading resumes.</option>';
            showAlert("Error loading your resumes. Please refresh or check connection.", 'danger');
        }
    };

    const renderScoreCircle = (overallScore, scoreLevel) => {
        const ring = document.getElementById('overall-ring');
        const textEl = document.getElementById('overall-val');
        const badgeEl = document.getElementById('score-level-badge');

        const clampedScore = Math.max(0, Math.min(100, overallScore || 0));
        textEl.textContent = clampedScore;

        // Circumference of 70r circle is ~440
        const offset = 440 - (440 * clampedScore) / 100;
        ring.style.strokeDashoffset = offset;

        // Score color and badge setting
        if (clampedScore >= 90) {
            ring.style.stroke = "#388e3c"; // green
            badgeEl.style.background = "rgba(56, 142, 60, 0.15)";
            badgeEl.style.color = "#81c784";
            badgeEl.style.borderColor = "rgba(56, 142, 60, 0.3)";
            badgeEl.textContent = scoreLevel || "Excellent ATS Compatibility";
        } else if (clampedScore >= 75) {
            ring.style.stroke = "#6366f1"; // indigo
            badgeEl.style.background = "rgba(99, 102, 241, 0.15)";
            badgeEl.style.color = "#818cf8";
            badgeEl.style.borderColor = "rgba(99, 102, 241, 0.3)";
            badgeEl.textContent = scoreLevel || "Strong ATS Compatibility";
        } else if (clampedScore >= 60) {
            ring.style.stroke = "#f59e0b"; // amber
            badgeEl.style.background = "rgba(245, 158, 11, 0.15)";
            badgeEl.style.color = "#fbbf24";
            badgeEl.style.borderColor = "rgba(245, 158, 11, 0.3)";
            badgeEl.textContent = scoreLevel || "Needs Improvement";
        } else if (clampedScore >= 40) {
            ring.style.stroke = "#f97316"; // orange
            badgeEl.style.background = "rgba(249, 115, 22, 0.15)";
            badgeEl.style.color = "#fb923c";
            badgeEl.style.borderColor = "rgba(249, 115, 22, 0.3)";
            badgeEl.textContent = scoreLevel || "Poor ATS Compatibility";
        } else {
            ring.style.stroke = "#d32f2f"; // red
            badgeEl.style.background = "rgba(211, 47, 47, 0.15)";
            badgeEl.style.color = "#e57373";
            badgeEl.style.borderColor = "rgba(211, 47, 47, 0.3)";
            badgeEl.textContent = scoreLevel || "Very Poor ATS Compatibility";
        }
    };

    const renderBreakdownMetrics = (data) => {
        const metrics = [
            { id: 'keyword', val: data.keyword_score || 0, max: 25 },
            { id: 'skills', val: data.skills_score || data.keyword_score || 0, max: 20 },
            { id: 'experience', val: data.experience_score || 0, max: 15 },
            { id: 'structure', val: data.structure_score || data.grammar_score || 0, max: 15 },
            { id: 'formatting', val: data.formatting_score || data.format_score || 0, max: 10 },
            { id: 'education', val: data.education_score || 8, max: 10 },
            { id: 'achievements', val: data.achievements_score || 4, max: 5 }
        ];

        metrics.forEach(m => {
            const valEl = document.getElementById(`val-${m.id}`);
            const fillEl = document.getElementById(`fill-${m.id}`);
            if (valEl && fillEl) {
                valEl.textContent = `${m.val}/${m.max}`;
                const pct = Math.min(100, Math.round((m.val / m.max) * 100));
                fillEl.style.width = `${pct}%`;
            }
        });
    };

    const renderBadges = (containerId, items, badgeClass) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">None detected</span>';
            return;
        }
        items.forEach(item => {
            const span = document.createElement('span');
            span.className = `badge-pill ${badgeClass}`;
            span.textContent = item;
            container.appendChild(span);
        });
    };

    const renderAtsDetails = (payload) => {
        hideAlert();
        resultsWrapper.style.display = 'grid';

        const data = payload.ats_result || payload;
        const results = data.ats_results || {};

        // 1. Render main circle and score badge
        renderScoreCircle(data.overall_score, data.score_level);

        // 2. Render sub-scores breakdown
        renderBreakdownMetrics(data);

        // 3. Render ATS Warnings
        const warningsContainer = document.getElementById('warnings-container');
        const warningsList = document.getElementById('ats-warnings-list');
        const warnings = results.ats_warnings || data.ats_warnings || [];
        
        if (warningsList && warnings.length > 0) {
            warningsContainer.style.display = 'block';
            warningsList.innerHTML = '';
            warnings.forEach(w => {
                const item = document.createElement('div');
                item.className = 'warning-card';
                item.innerHTML = `
                    <svg class="warning-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                    <span style="font-size:0.85rem; color:#f87171;">${w}</span>
                `;
                warningsList.appendChild(item);
            });
        } else if (warningsContainer) {
            warningsContainer.style.display = 'none';
        }

        // 4. Render Keywords Audit Badges
        const kwAnalysis = results.keyword_analysis || {};
        renderBadges('found-keywords-badges', kwAnalysis.found_keywords || [], 'badge-pill--success');
        renderBadges('missing-keywords-badges', kwAnalysis.missing_keywords || [], 'badge-pill--danger');

        // 5. Render Top Recommendations
        const recsList = document.getElementById('ats-recs-list');
        if (recsList) {
            recsList.innerHTML = '';
            const recs = results.overall_recommendations || data.recommendations || [];
            if (recs.length === 0) {
                recsList.innerHTML = '<li>Your resume complies well with standard ATS metrics! No urgent adjustments needed.</li>';
            } else {
                recs.forEach(rec => {
                    const li = document.createElement('li');
                    li.textContent = rec;
                    recsList.appendChild(li);
                });
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
                renderAtsDetails(data);
            }
        } catch (e) {
            // Ignore error if no past evaluation exists
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const resumeId = resumeSelect.value;
        if (!resumeId) {
            showAlert("Please select a valid resume to analyze.", 'warning');
            return;
        }

        // Disable button and show loading state
        btnRunAts.disabled = true;
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Analyzing your resume for ATS compatibility...';

        try {
            const token = await getAuthToken();
            
            // Call dedicated ATS analysis endpoint
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

            renderAtsDetails(data);
            showAlert("ATS analysis completed successfully.", 'success');
        } catch (err) {
            showAlert(err.message || "An unexpected error occurred during ATS analysis.", 'danger');
        } finally {
            btnRunAts.disabled = false;
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.textContent = 'Analyze ATS';
        }
    });

    populateDropdown().then(loadLatestScore);
});