import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('roadmap-resume-select') || document.getElementById('resume-select');
    const targetRoleInput = document.getElementById('roadmap-target-role') || document.getElementById('career-goal-input');
    const btnGenerate = document.getElementById('btn-generate-roadmap') || document.getElementById('btn-generate-plan');
    const form = document.getElementById('roadmap-setup-form') || document.getElementById('roadmap-form');
    const alertBox = document.getElementById('roadmap-alert-box');
    const statusMsg = document.getElementById('roadmap-status-msg') || document.getElementById('roadmap-status');

    // Workspace Results Elements
    const resultsContainer = document.getElementById('roadmap-workspace-results') || document.getElementById('roadmap-results-container');
    const readinessScoreEl = document.getElementById('roadmap-readiness-score') || document.getElementById('readiness-val');
    const readinessLabelEl = document.getElementById('roadmap-readiness-label') || document.getElementById('readiness-badge');
    const progressPercentEl = document.getElementById('roadmap-progress-percent') || document.getElementById('progress-pct');
    const progressBarFillEl = document.getElementById('roadmap-progress-bar-fill') || document.getElementById('progress-fill');
    const phasesContainer = document.getElementById('roadmap-phases-container') || document.getElementById('phases-list');
    const projectsListEl = document.getElementById('roadmap-projects-list') || document.getElementById('portfolio-projects-list');
    const prioritySkillsEl = document.getElementById('roadmap-priority-skills') || document.getElementById('priority-skills-container');

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

    const populateResumes = async () => {
        const selectContainer = document.getElementById('roadmap-resume-select-container') || document.getElementById('resume-select-container');
        if (selectContainer) renderSelectionSkeleton(selectContainer, 1, "Loading options...");

        try {
            const token = await getAuthToken();
            if (!token) {
                renderResumeCards(selectContainer, resumeSelect, []);
                return;
            }

            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to load resumes.");
            const data = await res.json();

            renderResumeCards(selectContainer, resumeSelect, data);

        } catch (err) {
            console.error("Resume dropdown error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", populateResumes);
            }
        }
    };

    const renderRoadmapDetails = (payload) => {
        hideAlert();
        if (resultsContainer) resultsContainer.style.display = 'grid';

        const data = payload.roadmap_data || payload.roadmap || payload;

        // Readiness Score
        const score = typeof data.readiness_score === 'number' ? data.readiness_score : 75;
        const level = data.readiness_level || (score >= 80 ? "Advanced Ready" : (score >= 60 ? "Intermediate Ready" : "Beginner"));

        if (readinessScoreEl) readinessScoreEl.textContent = `${score}/100`;
        if (readinessLabelEl) readinessLabelEl.textContent = level;

        // Phases
        if (phasesContainer) {
            phasesContainer.innerHTML = '';
            const phases = data.roadmap || data.phases || [];
            if (phases.length > 0) {
                phases.forEach((p, idx) => {
                    const phaseCard = document.createElement('div');
                    phaseCard.className = 'card';
                    phaseCard.style.padding = '1.25rem';
                    
                    const topicsList = (p.topics || p.milestones || []).map(t => `<li class="analysis-list-item">${t}</li>`).join('');

                    phaseCard.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                            <h4 style="font-size: 1.1rem; font-weight: 700; color: var(--primary);">Phase ${idx + 1}: ${p.phase_name || p.title || 'Learning Phase'}</h4>
                            <span class="badge badge-info">${p.estimated_duration || '2-4 Weeks'}</span>
                        </div>
                        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.75rem;">${p.description || p.focus_area || ''}</p>
                        <ul class="analysis-list">${topicsList}</ul>
                    `;
                    phasesContainer.appendChild(phaseCard);
                });
            } else {
                phasesContainer.innerHTML = '<div style="color:var(--text-muted);">No roadmap phases generated yet.</div>';
            }
        }

        // Projects
        if (projectsListEl) {
            projectsListEl.innerHTML = '';
            const projects = data.recommended_projects || data.projects || [];
            if (projects.length > 0) {
                projects.forEach((proj, idx) => {
                    const li = document.createElement('li');
                    li.className = 'rec-item';
                    li.innerHTML = `<div class="rec-counter-num">${idx + 1}</div><div class="rec-text">${proj}</div>`;
                    projectsListEl.appendChild(li);
                });
            } else {
                projectsListEl.innerHTML = '<li style="color:var(--text-muted); list-style:none;">Build portfolio projects matching your target role.</li>';
            }
        }

        // Priority Skills
        if (prioritySkillsEl) {
            prioritySkillsEl.innerHTML = '';
            const skills = data.priority_skills || data.missing_skills || [];
            if (skills.length > 0) {
                skills.forEach(s => {
                    const span = document.createElement('span');
                    span.className = 'badge badge--missing';
                    span.textContent = s;
                    prioritySkillsEl.appendChild(span);
                });
            } else {
                prioritySkillsEl.innerHTML = '<span style="color:var(--text-muted); font-size:0.85rem;">None</span>';
            }
        }
    };

    const loadLatestRoadmap = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/roadmap/latest`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data && (data.roadmap_data || data.roadmap)) {
                    renderRoadmapDetails(data);
                }
            }
        } catch (e) {
            // Ignore error if no past roadmap exists
        }
    };

    const generateRoadmap = async () => {
        const targetRole = targetRoleInput ? targetRoleInput.value.trim() : '';
        const resumeId = resumeSelect ? resumeSelect.value : null;

        if (!targetRole) {
            showAlert("Please enter your target career goal or role title.", 'danger');
            return;
        }

        if (btnGenerate) btnGenerate.disabled = true;
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'Generating personalized career roadmap...';
        }

        try {
            const token = await getAuthToken();

            const res = await fetch(`${API_BASE_URL}/api/roadmap/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    target_role: targetRole,
                    resume_id: resumeId
                })
            });

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to generate career roadmap.");
            }

            if (statusMsg) statusMsg.style.display = 'none';
            renderRoadmapDetails(data);
            showAlert("Career roadmap generated successfully.", 'success');
        } catch (err) {
            if (statusMsg) statusMsg.style.display = 'none';
            showAlert(err.message || "An unexpected error occurred generating roadmap.", 'danger');
        } finally {
            if (btnGenerate) btnGenerate.disabled = false;
        }
    };

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            generateRoadmap();
        });
    }

    if (btnGenerate) {
        btnGenerate.addEventListener('click', (e) => {
            generateRoadmap();
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            populateResumes().then(loadLatestRoadmap);
        }

        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                populateResumes().then(loadLatestRoadmap);
            }
        });
    };

    init();
});