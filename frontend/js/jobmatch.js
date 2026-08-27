import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';
import { API_BASE_URL } from './config.js';

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('jobmatch-resume-select') || document.getElementById('resume-select');
    const jobTitleInput = document.getElementById('job-title-input');
    const jobDescInput = document.getElementById('job-description-input') || document.getElementById('job-desc-input');
    const btnRunMatch = document.getElementById('btn-run-jobmatch') || document.getElementById('btn-run-match');
    const statusMsg = document.getElementById('jobmatch-status-msg') || document.getElementById('match-status-msg');
    const form = document.getElementById('jobmatch-form') || document.getElementById('job-match-form');
    const alertBox = document.getElementById('jobmatch-alert-box') || document.getElementById('match-alert-box');
    const resultsWrapper = document.getElementById('jobmatch-results-wrapper') || document.getElementById('match-results-wrapper');

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

    const populateResumes = async () => {
        const selectContainer = document.getElementById('jobmatch-resume-select-container') || document.getElementById('resume-select-container');
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

    const renderBadges = (containerId, items, typeClass) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<span style="font-size:0.85rem; color:var(--text-muted);">None detected</span>';
            return;
        }
        items.forEach(item => {
            const name = typeof item === 'string' ? item : (item.skill || item.name || JSON.stringify(item));
            const span = document.createElement('span');
            span.className = `badge badge--${typeClass}`;
            span.textContent = name;
            container.appendChild(span);
        });
    };

    const displayResults = (payload) => {
        hideAlert();
        if (resultsWrapper) resultsWrapper.style.display = 'grid';

        const data = payload.job_match || payload.analysis || payload;

        const score = typeof data.match_score === 'number' ? data.match_score : 75;
        const level = data.qualification_level || data.match_level || (score >= 90 ? "Excellent Fit" : (score >= 75 ? "Good Match" : "Moderate Fit"));

        const scoreEl = document.getElementById('res-match-score') || document.getElementById('res-score-val');
        if (scoreEl) scoreEl.textContent = `${score}%`;

        const badgeEl = document.getElementById('res-qualification-badge') || document.getElementById('res-match-level');
        if (badgeEl) badgeEl.textContent = level;

        const summaryEl = document.getElementById('res-match-summary') || document.getElementById('res-summary-text');
        if (summaryEl) summaryEl.textContent = data.summary || data.analysis_summary || `Your qualification fit score for this target position is ${score}%.`;

        // Render matching & missing skills badges
        const matched = data.matched_skills || data.matching_skills || [];
        const missing = (data.missing_skills || []).map(s => typeof s === 'string' ? s : s.skill);
        renderBadges('res-matching-skills', matched, 'technical');
        renderBadges('res-missing-skills', missing, 'missing');

        // Render AI-Inferred Recommended Skills for short job descriptions
        renderBadges('res-recommended-skills', data.recommended_skills || [], 'soft');

        // Render Programming Languages Status
        const langContainer = document.getElementById('res-languages-list');
        if (langContainer) {
            langContainer.innerHTML = '';
            const langs = data.programming_languages || [];
            if (langs.length > 0) {
                langs.forEach(l => {
                    const name = typeof l === 'string' ? l : l.name;
                    const status = typeof l === 'object' ? (l.status || 'Moderate') : 'Moderate';
                    const badgeType = status.toLowerCase().includes('strong') ? 'technical' : (status.toLowerCase().includes('missing') ? 'missing' : 'soft');

                    const span = document.createElement('span');
                    span.className = `badge badge--${badgeType}`;
                    span.textContent = `${name} (${status})`;
                    langContainer.appendChild(span);
                });
            } else {
                langContainer.innerHTML = '<span style="font-size:0.85rem; color:var(--text-muted);">None specified</span>';
            }
        }

        // Render Skill Gap Analysis Table
        const tbody = document.getElementById('res-skill-gap-tbody');
        if (tbody) {
            tbody.innerHTML = '';
            const skillGaps = data.skill_gap_analysis || data.missing_skills || data.skill_gaps || [];
            if (skillGaps.length > 0) {
                skillGaps.forEach(g => {
                    const skillName = typeof g === 'string' ? g : (g.skill || 'Skill');
                    const priority = typeof g === 'object' ? (g.priority || g.importance || 'High') : 'High';
                    const whyNeeded = typeof g === 'object' ? (g.why_needed || g.reason || '') : '';
                    const learnList = typeof g === 'object' && Array.isArray(g.what_to_learn) ? g.what_to_learn.join(', ') : (g.what_to_learn || '');
                    const task = typeof g === 'object' ? (g.practice_project || g.practical_task || g.recommendation || '') : '';

                    const prioClass = priority.toUpperCase() === 'HIGH' ? 'danger' : (priority.toUpperCase() === 'MEDIUM' ? 'warning' : 'info');

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${skillName}</strong><br><span style="font-size:0.82rem; color:var(--text-muted);">${whyNeeded}</span></td>
                        <td><span class="badge badge-${prioClass}">${priority.toUpperCase()}</span></td>
                        <td>
                            ${learnList ? `<div><strong>Learn:</strong> ${learnList}</div>` : ''}
                            ${task ? `<div style="margin-top:0.25rem;"><strong>Practice Task:</strong> ${task}</div>` : ''}
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">No major skill gaps identified!</td></tr>';
            }
        }

        // Render Top 5 Priority Improvements / Improvement Plan
        const topImpList = document.getElementById('res-top-improvements');
        if (topImpList) {
            topImpList.innerHTML = '';
            const top5 = data.improvement_plan || data.top_5_improvements || [];
            if (top5.length > 0) {
                top5.forEach((imp, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    const itemText = typeof imp === 'string' ? imp : `${imp.action || imp.item || ''} (${imp.priority || 'High'}) — ${imp.reason || ''}`;
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${itemText}</div>`;
                    topImpList.appendChild(li);
                });
            } else {
                topImpList.innerHTML = '<li style="color:var(--text-muted); list-style:none;">No critical top 5 improvements needed.</li>';
            }
        }

        // Render Recommended Learning Sequence
        const learnOrderList = document.getElementById('res-learning-order');
        if (learnOrderList) {
            learnOrderList.innerHTML = '';
            const order = data.recommended_learning_order || [];
            if (order.length > 0) {
                order.forEach((step, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    const stepText = typeof step === 'string' ? step : `Step ${step.step || idx + 1}: ${step.title || ''} — Focus: ${step.focus || ''}`;
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${stepText}</div>`;
                    learnOrderList.appendChild(li);
                });
            } else {
                learnOrderList.innerHTML = '<li style="color:var(--text-muted); list-style:none;">Sequential learning order will generate based on target job description.</li>';
            }
        }

        // Render Certifications List
        const certsList = document.getElementById('res-certifications-list');
        if (certsList) {
            certsList.innerHTML = '';
            const certs = data.certifications || data.certification_requirements || [];
            if (certs.length > 0) {
                certs.forEach((c, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    const certText = typeof c === 'string' ? c : `<strong>${c.name}</strong> (${c.provider || 'Provider'}) — Level: ${c.level || 'Recommended'} — ${c.reason || ''}`;
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${certText}</div>`;
                    certsList.appendChild(li);
                });
            } else {
                certsList.innerHTML = '<li style="color:var(--text-muted); list-style:none;">Certification not necessary; practical project experience would provide more value.</li>';
            }
        }

        // Render Practical Projects List
        const projectsList = document.getElementById('res-projects-list');
        if (projectsList) {
            projectsList.innerHTML = '';
            const projects = data.project_recommendations || data.projects_to_build || [];
            if (projects.length > 0) {
                projects.forEach((proj, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    const projText = typeof proj === 'string' ? proj : `<strong>${proj.title}</strong> — ${proj.what_to_build || proj.description || ''} (Target Skills: ${proj.skills_gained || proj.target_skill || 'Core Skills'})`;
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${projText}</div>`;
                    projectsList.appendChild(li);
                });
            } else {
                projectsList.innerHTML = '<li style="color:var(--text-muted); list-style:none;">Build portfolio projects matching missing skills.</li>';
            }
        }

        // Render Final Recommendation Paragraph
        const finalAdvEl = document.getElementById('res-final-advice');
        if (finalAdvEl) {
            finalAdvEl.textContent = data.final_recommendation || data.summary || 'Focus on building practical projects for your missing skill gaps to improve recruiter interest.';
        }

        // Render Recommendations List
        const recsList = document.getElementById('res-match-recommendations');
        if (recsList) {
            recsList.innerHTML = '';
            const recs = data.recommendations || [];
            if (recs.length > 0) {
                recs.forEach((r, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${r}</div>`;
                    recsList.appendChild(li);
                });
            } else {
                recsList.innerHTML = '<li style="color: var(--text-muted); list-style: none;">No additional recommendations required.</li>';
            }
        }
    };

    const runMatchAnalysis = async () => {
        const resumeId = resumeSelect ? resumeSelect.value : null;
        const jobTitle = jobTitleInput ? jobTitleInput.value.trim() : '';
        const jobDesc = jobDescInput ? jobDescInput.value.trim() : '';

        if (!resumeId) {
            showAlert("Please select a resume.", 'danger');
            return;
        }
        if (!jobDesc) {
            showAlert("Please enter target job description or role requirements.", 'danger');
            return;
        }

        if (btnRunMatch) btnRunMatch.disabled = true;
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'Comparing resume with job description...';
        }

        try {
            const token = await getAuthToken();

            const res = await fetch(`${API_BASE_URL}/api/jobmatch/analyze`, {
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

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to complete job match evaluation.");
            }

            if (statusMsg) statusMsg.style.display = 'none';
            displayResults(data);
            showAlert("Job match evaluation completed successfully.", 'success');
        } catch (err) {
            if (statusMsg) statusMsg.style.display = 'none';
            showAlert(err.message || "An unexpected error occurred during job matching.", 'danger');
        } finally {
            if (btnRunMatch) btnRunMatch.disabled = false;
        }
    };

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            runMatchAnalysis();
        });
    }

    if (btnRunMatch) {
        btnRunMatch.addEventListener('click', (e) => {
            runMatchAnalysis();
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