import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const setupForm = document.getElementById('roadmap-setup-form');
    const careerGoalInput = document.getElementById('roadmap-target-role') || document.getElementById('career-goal-input');
    const resumeSelect = document.getElementById('roadmap-resume-select');
    const btnGenerateRoadmap = document.getElementById('btn-generate-roadmap');
    const genStatusMsg = document.getElementById('roadmap-status-msg') || document.getElementById('gen-status-msg');
    const alertBox = document.getElementById('roadmap-alert-box');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    const loadResumes = async () => {
        const selectContainer = document.getElementById('roadmap-resume-select-container');
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
            console.error("Roadmap resume load error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", loadResumes);
            }
        }
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

    // 1. Render Roadmap Dashboard Results
    const renderRoadmapDetails = (data) => {
        currentRoadmap = data;
        hideAlert();
        resultsWrapper.style.display = 'block';

        const goal = data.career_goal || data.goal || "Target Career Roadmap";
        const readiness = data.readiness_score ?? 60;
        const readinessLabel = data.readiness_label || "Developing";
        const progress = data.progress ?? 0;

        resGoalTitle.textContent = `${goal} Roadmap`;
        resProfileSummary.textContent = data.current_profile_summary || "Personalized learning roadmap generated from your career profile and job matches.";
        resTimelineBadge.textContent = `Timeline: ${data.estimated_timeline || '4–8 weeks'}`;

        resReadinessVal.textContent = readiness;
        resReadinessLabel.textContent = readinessLabel;

        resProgressBar.style.width = `${progress}%`;
        resProgressPct.textContent = `${progress}%`;

        // Strengths
        resStrengthsUl.innerHTML = '';
        (data.current_strengths || []).forEach(s => {
            const li = document.createElement('li');
            li.textContent = s;
            resStrengthsUl.appendChild(li);
        });

        // Gaps
        resGapsUl.innerHTML = '';
        (data.priority_gaps || []).forEach(g => {
            const li = document.createElement('li');
            li.textContent = g;
            resGapsUl.appendChild(li);
        });

        // Phases Timeline Cards
        resPhasesContainer.innerHTML = '';
        const phases = data.roadmap || (data.roadmap_json ? data.roadmap_json.milestones : []) || [];
        
        if (phases.length === 0) {
            resPhasesContainer.innerHTML = '<p style="color:var(--text-muted);">No roadmap phases generated.</p>';
        } else {
            phases.forEach((p, index) => {
                const card = document.createElement('div');
                card.className = 'phase-card';

                const phaseTitle = p.title || p.phase || `Phase ${index + 1}`;
                const skillsStr = (p.skills_to_develop || p.topics || []).map(sk => `<span class="phase-badge">${sk}</span>`).join(' ');
                const statusVal = p.status || 'not_started';

                card.innerHTML = `
                    <div class="phase-meta">
                        <div style="display:flex; align-items:center; gap:0.65rem; flex-wrap:wrap;">
                            <span class="phase-badge" style="background:var(--primary-color); color:#fff;">Phase ${p.phase || index + 1}</span>
                            <h4 style="font-size:1.1rem; font-weight:700; color:var(--text-color);">${phaseTitle}</h4>
                        </div>
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <label style="font-size:0.85rem; color:var(--text-muted);">Status:</label>
                            <select class="form-input phase-status-select" data-index="${index}" style="padding:0.25rem 0.6rem; font-size:0.85rem; width:auto;">
                                <option value="not_started" ${statusVal === 'not_started' ? 'selected' : ''}>Not Started</option>
                                <option value="in_progress" ${statusVal === 'in_progress' ? 'selected' : ''}>In Progress</option>
                                <option value="completed" ${statusVal === 'completed' ? 'selected' : ''}>Completed</option>
                            </select>
                        </div>
                    </div>

                    ${p.objective ? `<p style="font-size:0.92rem; color:var(--text-color);"><strong>Objective:</strong> ${p.objective}</p>` : ''}
                    ${p.reason ? `<p style="font-size:0.88rem; color:var(--text-muted); font-style:italic;">Why This Comes First: ${p.reason}</p>` : ''}

                    ${skillsStr ? `<div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; margin-top:0.25rem;"><strong>Skills Focus:</strong> ${skillsStr}</div>` : ''}

                    <div class="two-col-grid" style="gap:1rem; margin-top:0.5rem;">
                        ${(p.activities && p.activities.length) ? `
                            <div>
                                <strong style="font-size:0.85rem; color:var(--primary-color);">Learning Activities:</strong>
                                <ul style="padding-left:1.25rem; font-size:0.88rem; margin-top:0.25rem;">
                                    ${p.activities.map(a => `<li>${a}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${(p.project_ideas && p.project_ideas.length) ? `
                            <div>
                                <strong style="font-size:0.85rem; color:var(--primary-color);">Project Milestones:</strong>
                                <ul style="padding-left:1.25rem; font-size:0.88rem; margin-top:0.25rem;">
                                    ${p.project_ideas.map(proj => `<li>${proj}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                `;
                resPhasesContainer.appendChild(card);
            });

            // Handle Progress Status Change
            resPhasesContainer.querySelectorAll('.phase-status-select').forEach(sel => {
                sel.addEventListener('change', async (e) => {
                    const phaseIdx = parseInt(e.target.getAttribute('data-index'), 10);
                    const newStatus = e.target.value;

                    if (!currentRoadmap || !currentRoadmap.id) return;

                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/career-roadmap/${currentRoadmap.id}/progress`, {
                            method: 'PATCH',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${token}`
                            },
                            body: JSON.stringify({ phase_index: phaseIdx, status: newStatus })
                        });

                        const resData = await resp.json();
                        if (resp.ok) {
                            const updated = resData.roadmap || resData;
                            currentRoadmap = updated;
                            const newProgress = updated.progress ?? 0;
                            resProgressBar.style.width = `${newProgress}%`;
                            resProgressPct.textContent = `${newProgress}%`;
                            loadHistory();
                        }
                    } catch (err) {
                        console.error("Failed to update phase progress:", err);
                    }
                });
            });
        }

        // Projects
        resProjectsUl.innerHTML = '';
        (data.recommended_projects || []).forEach(p => {
            const li = document.createElement('li');
            li.textContent = p;
            resProjectsUl.appendChild(li);
        });

        // Checklist
        resChecklistUl.innerHTML = '';
        (data.job_readiness_checklist || []).forEach(c => {
            const li = document.createElement('li');
            li.textContent = c;
            resChecklistUl.appendChild(li);
        });

        resultsWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    // 2. Load History
    const loadHistory = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-roadmap`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const history = await res.json();

            historyList.innerHTML = '';
            if (!Array.isArray(history) || history.length === 0) {
                historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">No previous career roadmaps recorded.</p>';
                return;
            }

            history.forEach(item => {
                const card = document.createElement('div');
                card.className = 'history-card';

                const goal = item.career_goal || item.goal || 'Career Roadmap';
                const score = item.readiness_score ?? 60;
                const progress = item.progress ?? 0;
                const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent';

                card.innerHTML = `
                    <div>
                        <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
                            <h4 style="font-size:1rem; font-weight:600; color:var(--text-color);">${goal}</h4>
                            <span class="phase-badge" style="margin:0; padding:0.15rem 0.5rem; font-size:0.75rem;">Score: ${score}/100</span>
                        </div>
                        <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0.25rem;">Progress: ${progress}% &bull; Created on ${dateStr}</p>
                    </div>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn btn-secondary btn-view-roadmap" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem;">View</button>
                        <button class="btn btn-secondary btn-delete-roadmap" data-id="${item.id}" style="padding:0.4rem 0.85rem; font-size:0.85rem; color:var(--error-color); border-color:rgba(220,38,38,0.3);">Delete</button>
                    </div>
                `;
                historyList.appendChild(card);
            });

            // View click handler
            historyList.querySelectorAll('.btn-view-roadmap').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const roadmapId = e.currentTarget.getAttribute('data-id');
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/career-roadmap/${roadmapId}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to load roadmap.");
                        const record = await resp.json();
                        renderRoadmapDetails(record);
                    } catch (err) {
                        showAlert("Failed to load selected roadmap.");
                    }
                });
            });

            // Delete click handler
            historyList.querySelectorAll('.btn-delete-roadmap').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const roadmapId = e.currentTarget.getAttribute('data-id');
                    if (!confirm("Are you sure you want to delete this career roadmap?")) return;
                    try {
                        const token = await getAuthToken();
                        const resp = await fetch(`${API_BASE_URL}/api/career-roadmap/${roadmapId}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (!resp.ok) throw new Error("Failed to delete roadmap.");
                        loadHistory();
                    } catch (err) {
                        showAlert("Failed to delete selected roadmap.");
                    }
                });
            });

        } catch (err) {
            console.error("History load error:", err);
            historyList.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">Unable to load previous career roadmaps.</p>';
        }
    };

    // 3. Form Submit
    setupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const goalText = careerGoalInput.value.trim();

        btnGenerateRoadmap.disabled = true;
        btnGenerateRoadmap.querySelector('span').textContent = 'AI is analyzing your career profile and creating a personalized roadmap...';
        genStatusMsg.style.display = 'inline';
        genStatusMsg.textContent = 'Gathering resume, ATS, job matches, and skill gaps to build custom milestone roadmap...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-roadmap/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ career_goal: goalText })
            });

            const data = await res.json();
            if (!res.ok) {
                showAlert(data.error || "Career roadmap generation is temporarily unavailable. Please try again.");
                return;
            }

            const record = data.roadmap || data;
            renderRoadmapDetails(record);
            showAlert("Personalized AI Career Roadmap generated successfully!", false);
            loadHistory();

        } catch (err) {
            console.error("Roadmap generation error:", err);
            showAlert("Career roadmap generation is temporarily unavailable. Please try again.");
        } finally {
            btnGenerateRoadmap.disabled = false;
            btnGenerateRoadmap.querySelector('span').textContent = 'Generate Career Roadmap';
            genStatusMsg.style.display = 'none';
        }
    });

    // Initial load
    loadResumes();
    loadHistory();
});