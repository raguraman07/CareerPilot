import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const jobTitleInput = document.getElementById('job-title-input');
    const jobDescInput = document.getElementById('job-desc-input');
    const btnRunMatch = document.getElementById('btn-run-match');
    const statusMsg = document.getElementById('match-status-msg');
    const form = document.getElementById('job-match-form');
    const alertBox = document.getElementById('match-alert-box');
    const resultsWrapper = document.getElementById('match-results-wrapper');
    const historyList = document.getElementById('history-list');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
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

    // 1. Populate Resumes Dropdown
    const populateResumes = async () => {
        const selectContainer = document.getElementById('jobmatch-resume-select-container');
        if (btnRunMatch) btnRunMatch.disabled = true;
        if (selectContainer) renderSelectionSkeleton(selectContainer, 1, "Loading options...");

        try {
            const token = await getAuthToken();
            if (!token) {
                renderResumeCards(selectContainer, resumeSelect, [], (selectedId) => {
                    if (btnRunMatch) btnRunMatch.disabled = !selectedId;
                });
                return;
            }

            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to load resumes.");
            const data = await res.json();

            renderResumeCards(selectContainer, resumeSelect, data, (selectedId) => {
                if (btnRunMatch) btnRunMatch.disabled = !selectedId;
            });

        } catch (err) {
            console.error("Resume dropdown error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", populateResumes);
            }
            if (btnRunMatch) btnRunMatch.disabled = true;
        }
    };

    // 2. Render Results UI
    const displayResults = (data) => {
        hideAlert();
        resultsWrapper.style.display = 'flex';

        // Match Score & Level
        const score = typeof data.match_score === 'number' ? data.match_score : (data.match_percentage || 0);
        const level = data.match_level || (score >= 90 ? "Excellent Match" : (score >= 75 ? "Strong Match" : (score >= 60 ? "Moderate Match" : (score >= 40 ? "Low Match" : "Poor Match"))));

        const scoreValEl = document.getElementById('res-score-val');
        const matchLevelEl = document.getElementById('res-match-level');
        const jobTitleEl = document.getElementById('res-job-title');
        const summaryEl = document.getElementById('res-summary-text');

        scoreValEl.textContent = score;
        matchLevelEl.textContent = level;
        matchLevelEl.className = 'match-badge ' + (
            score >= 90 ? 'excellent' : (score >= 75 ? 'strong' : (score >= 60 ? 'moderate' : (score >= 40 ? 'low' : 'poor')))
        );

        jobTitleEl.textContent = data.job_title || "Target Position";
        summaryEl.textContent = data.summary || "Complete dynamic job match analysis comparing resume requirements against target job parameters.";

        // Matching Skills
        const matchingContainer = document.getElementById('res-matching-skills');
        matchingContainer.innerHTML = '';
        const matching = data.matching_skills || [];
        if (matching.length === 0) {
            matchingContainer.innerHTML = '<span style="color:var(--text-muted);font-size:0.87rem;">No matching skills identified.</span>';
        } else {
            matching.forEach(sk => {
                const span = document.createElement('span');
                span.className = 'skill-badge match';
                span.textContent = sk;
                matchingContainer.appendChild(span);
            });
        }

        // Missing Skills
        const missingContainer = document.getElementById('res-missing-skills');
        missingContainer.innerHTML = '';
        const missing = data.missing_skills || [];
        if (missing.length === 0) {
            missingContainer.innerHTML = '<span style="color:var(--text-muted);font-size:0.87rem;">No missing skills identified!</span>';
        } else {
            missing.forEach(sk => {
                const span = document.createElement('span');
                span.className = 'skill-badge missing';
                span.textContent = sk;
                missingContainer.appendChild(span);
            });
        }

        // Candidate Strengths
        const strengthsList = document.getElementById('res-candidate-strengths');
        strengthsList.innerHTML = '';
        const strengths = data.candidate_strengths || [];
        if (strengths.length === 0) {
            strengthsList.innerHTML = '<li>No key strengths highlighted.</li>';
        } else {
            strengths.forEach(s => {
                const li = document.createElement('li');
                li.textContent = s;
                strengthsList.appendChild(li);
            });
        }

        // Candidate Weaknesses
        const weaknessesList = document.getElementById('res-candidate-weaknesses');
        weaknessesList.innerHTML = '';
        const weaknesses = data.candidate_weaknesses || [];
        if (weaknesses.length === 0) {
            weaknessesList.innerHTML = '<li>No critical weaknesses identified.</li>';
        } else {
            weaknesses.forEach(w => {
                const li = document.createElement('li');
                li.textContent = w;
                weaknessesList.appendChild(li);
            });
        }

        // Experience Match
        const expEl = document.getElementById('res-exp-content');
        const expData = data.experience_match || {};
        expEl.innerHTML = `
            <div style="font-weight:600; color:var(--primary-color);">Alignment Score: ${expData.score ?? score}%</div>
            ${(expData.strengths && expData.strengths.length) ? `<div style="color:var(--text-color); margin-top:0.25rem;"><strong>Strengths:</strong> ${expData.strengths.join(', ')}</div>` : ''}
            ${(expData.gaps && expData.gaps.length) ? `<div style="color:var(--text-muted); margin-top:0.25rem;"><strong>Gaps:</strong> ${expData.gaps.join(', ')}</div>` : ''}
        `;

        // Education Match
        const eduEl = document.getElementById('res-edu-content');
        const eduData = data.education_match || {};
        eduEl.innerHTML = `
            <div style="font-weight:600; color:var(--primary-color);">Alignment Score: ${eduData.score ?? score}%</div>
            ${(eduData.strengths && eduData.strengths.length) ? `<div style="color:var(--text-color); margin-top:0.25rem;"><strong>Strengths:</strong> ${eduData.strengths.join(', ')}</div>` : ''}
            ${(eduData.gaps && eduData.gaps.length) ? `<div style="color:var(--text-muted); margin-top:0.25rem;"><strong>Gaps:</strong> ${eduData.gaps.join(', ')}</div>` : ''}
        `;

        // Qualification Match
        const qualEl = document.getElementById('res-qual-content');
        const qualData = data.qualification_match || {};
        qualEl.innerHTML = `
            <div style="font-weight:600; color:var(--primary-color);">Alignment Score: ${qualData.score ?? score}%</div>
            ${(qualData.strengths && qualData.strengths.length) ? `<div style="color:var(--text-color); margin-top:0.25rem;"><strong>Strengths:</strong> ${qualData.strengths.join(', ')}</div>` : ''}
            ${(qualData.gaps && qualData.gaps.length) ? `<div style="color:var(--text-muted); margin-top:0.25rem;"><strong>Gaps:</strong> ${qualData.gaps.join(', ')}</div>` : ''}
        `;

        // Skill Gap Table
        const tbody = document.getElementById('res-skill-gaps-tbody');
        tbody.innerHTML = '';
        const gaps = data.skill_gaps || [];
        if (gaps.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="color:var(--text-muted); text-align:center;">No significant skill gaps detected.</td></tr>`;
        } else {
            gaps.forEach(g => {
                const tr = document.createElement('tr');
                const imp = (g.importance || 'Medium').toLowerCase();
                tr.innerHTML = `
                    <td style="font-weight:600; color:var(--text-color);">${g.skill || 'Skill'}</td>
                    <td><span class="importance-badge ${imp}">${g.importance || 'Medium'}</span></td>
                    <td style="color:var(--text-muted);">${g.reason || 'N/A'}</td>
                    <td style="color:var(--text-color);">${g.recommendation || 'N/A'}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Recommendations List
        const recsList = document.getElementById('res-recommendations-list');
        recsList.innerHTML = '';
        const recs = data.recommendations || [];
        if (recs.length === 0) {
            recsList.innerHTML = '<li>No recommendations generated.</li>';
        } else {
            recs.forEach(r => {
                const li = document.createElement('li');
                li.textContent = r;
                recsList.appendChild(li);
            });
        }

        // Scroll cleanly to results
        resultsWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    // 3. Load History
    const loadHistory = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/job-matching/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const history = await res.json();

            historyList.innerHTML = '';
            if (!Array.isArray(history) || history.length === 0) {
                historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">No previous job matches recorded yet.</p>';
                return;
            }

            history.forEach(item => {
                const card = document.createElement('div');
                card.className = 'history-card';

                const score = item.match_score ?? (item.match_percentage || 0);
                const title = item.job_title || 'Target Job Match';
                const createdDate = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent';
                const filename = item.resume_filename || 'Resume';

                card.innerHTML = `
                    <div>
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <h4 style="font-size:1rem; font-weight:600; color:var(--text-color);">${title}</h4>
                            <span class="match-badge ${score >= 90 ? 'excellent' : (score >= 75 ? 'strong' : (score >= 60 ? 'moderate' : 'low'))}" style="margin:0; padding:0.15rem 0.5rem; font-size:0.75rem;">${score}%</span>
                        </div>
                        <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0.25rem;">Resume: ${filename} &bull; Analyzed on ${createdDate}</p>
                    </div>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-secondary btn-view-match" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem;">View</button>
                        <button class="btn btn-secondary btn-delete-match" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem; color:var(--error-color); border-color:rgba(220,38,38,0.3);">Delete</button>
                    </div>
                `;
                historyList.appendChild(card);
            });

            // View event handler
            historyList.querySelectorAll('.btn-view-match').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const matchId = e.currentTarget.getAttribute('data-id');
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/job-matching/${matchId}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to load match record.");
                        const record = await resp.json();
                        displayResults(record);
                    } catch (err) {
                        showAlert("Failed to retrieve selected job match details.");
                    }
                });
            });

            // Delete event handler
            historyList.querySelectorAll('.btn-delete-match').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const matchId = e.currentTarget.getAttribute('data-id');
                    if (!confirm("Are you sure you want to delete this job match analysis?")) return;
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/job-matching/${matchId}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to delete record.");
                        loadHistory();
                    } catch (err) {
                        showAlert("Failed to delete selected job match record.");
                    }
                });
            });

        } catch (err) {
            console.error("History load error:", err);
            historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">Unable to load previous job match history.</p>';
        }
    };

    // 4. Handle Form Submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const resumeId = resumeSelect.value;
        const jobTitle = jobTitleInput.value.trim();
        const jobDesc = jobDescInput.value.trim();

        if (!resumeId) {
            showAlert("Please select a resume.");
            return;
        }

        if (!jobDesc) {
            showAlert("Please paste a target job description.");
            return;
        }

        // Loading state
        btnRunMatch.disabled = true;
        btnRunMatch.querySelector('span').textContent = 'AI is comparing your resume with the job description...';
        statusMsg.style.display = 'inline';
        statusMsg.textContent = 'Analyzing resume and job requirements using Gemini...';

        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE_URL}/api/job-matching/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    resume_id: resumeId,
                    job_title: jobTitle,
                    job_description: jobDesc
                })
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMessage = data.error || "AI job matching is temporarily unavailable. Please try again.";
                showAlert(errorMessage);
                return;
            }

            const record = data.analysis || data;
            displayResults(record);
            showAlert("Job match analysis completed successfully!", false);
            loadHistory();

        } catch (err) {
            console.error("Job match submission error:", err);
            showAlert(err.message || "AI job matching is temporarily unavailable. Please try again.");
        } finally {
            btnRunMatch.disabled = false;
            btnRunMatch.querySelector('span').textContent = 'Analyze Job Match';
            statusMsg.style.display = 'none';
        }
    });

    // Initial load
    populateResumes();
    loadHistory();
});