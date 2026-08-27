import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    // Header & Action Elements
    const btnDownloadPdf = document.getElementById('btn-download-pdf');
    const btnGenerate = document.getElementById('btn-generate-roadmap');
    const btnGenerateText = document.getElementById('btn-generate-text');
    const alertBox = document.getElementById('roadmap-alert-box');

    // Career Goal Banner Elements
    const goalCard = document.getElementById('roadmap-goal-card');
    const goalDisplayCompany = document.getElementById('goal-display-company');
    const goalDisplayRole = document.getElementById('goal-display-role');
    const goalEmptyPrompt = document.getElementById('roadmap-empty-goal-prompt');
    const loadingStateCard = document.getElementById('roadmap-loading-state');
    const loadingTitle = document.getElementById('loading-state-title');

    // Workspace Results Elements
    const resultsContainer = document.getElementById('roadmap-workspace-results');
    const readinessScoreEl = document.getElementById('roadmap-readiness-score');
    const readinessLabelEl = document.getElementById('roadmap-readiness-label');
    const readinessSummaryEl = document.getElementById('roadmap-readiness-summary');
    const durationLabelEl = document.getElementById('roadmap-duration-label');
    const progressPercentEl = document.getElementById('roadmap-progress-percent');
    const progressBarFillEl = document.getElementById('roadmap-progress-bar-fill');

    // Detailed Section Containers
    const skillGapsTableBody = document.getElementById('roadmap-skill-gaps-table-body');
    const skillGapsCard = document.getElementById('roadmap-skill-gaps-card');
    const phasesContainer = document.getElementById('roadmap-phases-container');
    const languagesListEl = document.getElementById('roadmap-languages-list');
    const techListEl = document.getElementById('roadmap-technologies-list');
    const toolsListEl = document.getElementById('roadmap-tools-list');
    const subjectsListEl = document.getElementById('roadmap-subjects-list');
    const certsContainer = document.getElementById('roadmap-certifications-container');
    const projectsContainer = document.getElementById('roadmap-projects-container');
    const checklistContainer = document.getElementById('roadmap-checklist-container');

    let currentRoadmapId = null;
    let activeCareerGoal = null;

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    const showAlert = (message, type = 'danger') => {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        if (type === 'danger') {
            alertBox.style.background = 'rgba(198, 40, 40, 0.12)';
            alertBox.style.color = '#c62828';
            alertBox.style.border = '1px solid rgba(198, 40, 40, 0.3)';
        } else {
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

    // 1. Fetch Active Career Goal from Firestore
    const fetchActiveCareerGoal = async () => {
        try {
            const token = await getAuthToken();
            if (!token) return null;

            const res = await fetch(`${API_BASE_URL}/api/career-goals/current`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("Failed to fetch active career goal.");
            const data = await res.json();
            if (data.success && data.career_goal) {
                activeCareerGoal = data.career_goal;
                if (goalDisplayCompany) goalDisplayCompany.textContent = activeCareerGoal.company_name || 'Target Company';
                if (goalDisplayRole) goalDisplayRole.textContent = activeCareerGoal.job_role || 'Target Role';
                if (goalCard) goalCard.style.display = 'block';
                if (goalEmptyPrompt) goalEmptyPrompt.style.display = 'none';
                return activeCareerGoal;
            } else {
                if (goalCard) goalCard.style.display = 'none';
                if (goalEmptyPrompt) goalEmptyPrompt.style.display = 'block';
                return null;
            }
        } catch (err) {
            console.error("Error loading career goal:", err);
            return null;
        }
    };

    // 2. Render Full Structured Roadmap
    const renderRoadmapDetails = (payload) => {
        hideAlert();
        if (loadingStateCard) loadingStateCard.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'flex';
        if (btnDownloadPdf) btnDownloadPdf.style.display = 'inline-flex';

        const data = payload.roadmap_data || payload.roadmap || payload;
        currentRoadmapId = data.id || payload.roadmap_id || currentRoadmapId;

        // Career Goal Banner synchronization
        const cg = data.career_goal || {};
        const comp = typeof cg === 'object' ? (cg.company || 'Target Company') : 'Target Company';
        const role = typeof cg === 'object' ? (cg.role || 'Target Role') : (cg || 'Target Role');
        if (goalDisplayCompany) goalDisplayCompany.textContent = comp;
        if (goalDisplayRole) goalDisplayRole.textContent = role;
        if (goalCard) goalCard.style.display = 'block';
        if (goalEmptyPrompt) goalEmptyPrompt.style.display = 'none';

        // Readiness Score & Summary
        const readiness = data.current_readiness || {};
        const score = typeof readiness.score === 'number' ? readiness.score : (typeof data.readiness_score === 'number' ? data.readiness_score : 65);
        const label = data.readiness_label || (score >= 80 ? "Advanced Ready" : (score >= 60 ? "Developing" : "Early Stage"));
        const summary = readiness.summary || data.current_profile_summary || `Personalized career roadmap tailored for ${role} at ${comp}.`;
        const duration = data.roadmap_duration || data.estimated_timeline || "8–12 weeks";

        if (readinessScoreEl) readinessScoreEl.textContent = `${score}/100`;
        if (readinessLabelEl) readinessLabelEl.textContent = label;
        if (readinessSummaryEl) readinessSummaryEl.textContent = summary;
        if (durationLabelEl) durationLabelEl.textContent = `Estimated: ${duration}`;

        // Progress Calculation
        const progressPct = data.progress || 0;
        if (progressPercentEl) progressPercentEl.textContent = `${progressPct}%`;
        if (progressBarFillEl) progressBarFillEl.style.width = `${progressPct}%`;

        // 3. Render Identified Skill Gaps Table
        const skillGaps = data.skill_gaps || [];
        if (skillGapsTableBody && skillGapsCard) {
            skillGapsTableBody.innerHTML = '';
            if (skillGaps.length > 0) {
                skillGapsCard.style.display = 'block';
                skillGaps.forEach(gap => {
                    const sName = gap.skill || 'Skill';
                    const sImp = gap.importance || 'High';
                    const sReason = gap.reason || 'Critical requirement for target role.';
                    const sCurr = gap.current_level || 'Beginner';
                    const sTarg = gap.target_level || 'Production Ready';

                    let impBadge = `<span class="badge badge-danger">HIGH</span>`;
                    if (sImp.toLowerCase() === 'medium') impBadge = `<span class="badge badge-warning">MEDIUM</span>`;
                    if (sImp.toLowerCase() === 'low') impBadge = `<span class="badge badge-success">LOW</span>`;

                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid var(--border-light)';
                    tr.innerHTML = `
                        <td style="padding: 0.75rem 0.85rem; font-weight: 700; color: var(--dark);">${sName}</td>
                        <td style="padding: 0.75rem 0.85rem;">${impBadge}</td>
                        <td style="padding: 0.75rem 0.85rem; color: var(--text-secondary); max-width: 320px; line-height: 1.4;">${sReason}</td>
                        <td style="padding: 0.75rem 0.85rem; color: var(--dark); font-size: 0.84rem;">${sCurr}</td>
                        <td style="padding: 0.75rem 0.85rem; color: var(--primary); font-weight: 600; font-size: 0.84rem;">${sTarg}</td>
                    `;
                    skillGapsTableBody.appendChild(tr);
                });
            } else {
                skillGapsCard.style.display = 'none';
            }
        }

        // 4. Render Phases with Granular Progress
        const phases = data.phases || data.roadmap || [];
        if (phasesContainer) {
            phasesContainer.innerHTML = '';
            if (phases.length > 0) {
                phases.forEach((phase, pIdx) => {
                    const isPhaseCompleted = phase.status === 'completed';
                    const phaseCard = document.createElement('div');
                    phaseCard.className = 'card';
                    phaseCard.style.padding = '1.35rem';
                    phaseCard.style.borderLeft = isPhaseCompleted ? '4px solid var(--success)' : '4px solid var(--primary)';
                    phaseCard.style.backgroundColor = isPhaseCompleted ? 'rgba(232, 245, 233, 0.25)' : '#FFFFFF';

                    // Skills with Priority Badges
                    let skillsHtml = '';
                    const skills = phase.skills || [];
                    if (skills.length > 0) {
                        skillsHtml = skills.map((sk, sIdx) => {
                            const sName = typeof sk === 'object' ? sk.name : sk;
                            const sPrio = typeof sk === 'object' ? (sk.priority || 'High') : 'High';
                            const sReason = typeof sk === 'object' ? sk.reason : '';
                            const sLearn = typeof sk === 'object' ? sk.what_to_learn : '';
                            const isDone = typeof sk === 'object' && sk.status === 'completed';

                            let prioBadge = `<span class="badge badge-danger">🔴 HIGH PRIORITY</span>`;
                            if (sPrio.toLowerCase() === 'medium') prioBadge = `<span class="badge badge-warning">🟠 MEDIUM</span>`;
                            if (sPrio.toLowerCase() === 'low') prioBadge = `<span class="badge badge-success">🟢 LOW</span>`;

                            return `
                            <div style="background-color: var(--surface-secondary); padding: 0.85rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-light); margin-bottom: 0.65rem;">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap;">
                                    <label style="display: flex; align-items: center; gap: 0.65rem; cursor: pointer; font-weight: 600; color: var(--dark); font-size: 0.95rem;">
                                        <input type="checkbox" class="roadmap-item-checkbox" data-phase="${pIdx}" data-type="skill" data-index="${sIdx}" ${isDone ? 'checked' : ''} style="width: 17px; height: 17px; accent-color: var(--primary); cursor: pointer;">
                                        <span style="${isDone ? 'text-decoration: line-through; opacity: 0.75;' : ''}">${sName}</span>
                                    </label>
                                    ${prioBadge}
                                </div>
                                ${sReason ? `<p style="font-size: 0.84rem; color: var(--text-secondary); margin: 0.4rem 0 0 1.7rem; line-height: 1.4;"><strong>Why:</strong> ${sReason}</p>` : ''}
                                ${sLearn ? `<p style="font-size: 0.84rem; color: var(--dark); margin: 0.2rem 0 0 1.7rem; line-height: 1.4;"><strong>What to Learn:</strong> ${sLearn}</p>` : ''}
                            </div>
                            `;
                        }).join('');
                    }

                    // Milestone block
                    const milestone = phase.milestone || '';

                    phaseCard.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.85rem;">
                            <div style="display: flex; align-items: center; gap: 0.75rem;">
                                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                                    <input type="checkbox" class="roadmap-phase-checkbox" data-phase="${pIdx}" ${isPhaseCompleted ? 'checked' : ''} style="width: 19px; height: 19px; accent-color: var(--primary); cursor: pointer;">
                                    <h4 style="font-size: 1.15rem; font-weight: 700; color: var(--dark); margin: 0;">Phase ${phase.phase_number || (pIdx + 1)}: ${phase.title || 'Learning Phase'}</h4>
                                </label>
                            </div>
                            <span class="badge badge-info" style="font-weight: 600;">${phase.duration || '2-3 Weeks'}</span>
                        </div>
                        ${phase.objective ? `<p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.5;">${phase.objective}</p>` : ''}
                        ${skillsHtml ? `<div style="margin-bottom: 1rem;">${skillsHtml}</div>` : ''}
                        ${milestone ? `
                            <div style="background-color: rgba(252, 242, 229, 0.6); border: 1px dashed var(--border); border-radius: var(--radius-sm); padding: 0.65rem 0.85rem; font-size: 0.85rem; color: var(--dark);">
                                <strong>🎯 Phase Milestone:</strong> ${milestone}
                            </div>
                        ` : ''}
                    `;
                    phasesContainer.appendChild(phaseCard);
                });
            }
        }

        // 5. Aggregate & Render Languages, Technologies, Tools, Subjects
        const allLangs = new Set();
        const allTechs = new Set();
        const allTools = new Set();
        const allSubjects = new Set();
        const allCerts = [];
        const seenCerts = new Set();
        const allProjects = [];

        phases.forEach(ph => {
            (ph.languages || []).forEach(l => allLangs.add(l));
            (ph.technologies || []).forEach(t => allTechs.add(t));
            (ph.tools || []).forEach(tl => allTools.add(tl));
            (ph.core_subjects || []).forEach(s => allSubjects.add(s));
            (ph.certifications || []).forEach(c => {
                const cName = typeof c === 'object' ? c.name : c;
                if (cName && !seenCerts.has(cName)) {
                    seenCerts.add(cName);
                    allCerts.push(c);
                }
            });
            (ph.projects || []).forEach(pr => allProjects.push(pr));
        });

        // Languages List
        if (languagesListEl) {
            languagesListEl.innerHTML = '';
            if (allLangs.size > 0) {
                allLangs.forEach(l => {
                    const span = document.createElement('span');
                    span.className = 'skill-badge badge--technical';
                    span.textContent = `✓ ${l}`;
                    languagesListEl.appendChild(span);
                });
            } else {
                languagesListEl.innerHTML = '<span class="text-muted" style="font-size:0.85rem;">No additional languages required for this role.</span>';
            }
        }

        // Technologies List
        if (techListEl) {
            techListEl.innerHTML = '';
            if (allTechs.size > 0) {
                allTechs.forEach(t => {
                    const span = document.createElement('span');
                    span.className = 'skill-badge';
                    span.textContent = t;
                    techListEl.appendChild(span);
                });
            } else {
                techListEl.innerHTML = '<span class="text-muted" style="font-size:0.85rem;">No specific technologies listed.</span>';
            }
        }

        // Tools List
        if (toolsListEl) {
            toolsListEl.innerHTML = '';
            if (allTools.size > 0) {
                allTools.forEach(tl => {
                    const span = document.createElement('span');
                    span.className = 'skill-badge badge--soft';
                    span.textContent = tl;
                    toolsListEl.appendChild(span);
                });
            } else {
                toolsListEl.innerHTML = '<span class="text-muted" style="font-size:0.85rem;">No additional tools required.</span>';
            }
        }

        // Core Subjects List
        if (subjectsListEl) {
            subjectsListEl.innerHTML = '';
            if (allSubjects.size > 0) {
                allSubjects.forEach(s => {
                    const li = document.createElement('li');
                    li.className = 'analysis-list-item';
                    li.textContent = s;
                    subjectsListEl.appendChild(li);
                });
            } else {
                subjectsListEl.innerHTML = '<li class="analysis-list-item" style="color: var(--text-muted);">Practical project execution prioritized over academic subjects.</li>';
            }
        }

        // Certifications Container
        if (certsContainer) {
            certsContainer.innerHTML = '';
            if (allCerts.length > 0) {
                allCerts.forEach(cert => {
                    const cName = typeof cert === 'object' ? cert.name : cert;
                    const cProv = typeof cert === 'object' ? (cert.provider || comp) : comp;
                    const cPrio = typeof cert === 'object' ? (cert.priority || 'High') : 'High';
                    const cReason = typeof cert === 'object' ? cert.reason : '';
                    const cUrl = typeof cert === 'object' ? (cert.url || cert.official_url) : '';

                    const cDiv = document.createElement('div');
                    cDiv.style.backgroundColor = 'var(--surface-secondary)';
                    cDiv.style.border = '1px solid var(--border-light)';
                    cDiv.style.borderRadius = 'var(--radius-sm)';
                    cDiv.style.padding = '0.85rem 1rem';

                    cDiv.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--dark); margin: 0;">${cName}</h4>
                                <span style="font-size: 0.8rem; color: var(--text-muted);">Provider: ${cProv}</span>
                            </div>
                            <span class="badge badge-danger" style="font-size: 0.75rem;">${cPrio.toUpperCase()} PRIORITY</span>
                        </div>
                        ${cReason ? `<p style="font-size: 0.84rem; color: var(--dark); margin: 0.4rem 0 0 0; line-height: 1.4;">${cReason}</p>` : ''}
                        ${cUrl ? `<div style="margin-top: 0.5rem;"><a href="${cUrl}" target="_blank" rel="noopener noreferrer" style="font-size: 0.82rem; font-weight: 600; color: var(--primary); text-decoration: underline;">Official Certification Details ↗</a></div>` : ''}
                    `;
                    certsContainer.appendChild(cDiv);
                });
            } else {
                certsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.88rem;">Focus directly on hands-on practical project portfolio demonstration.</div>';
            }
        }

        // Projects Container (Beginner -> Intermediate -> Advanced)
        if (projectsContainer) {
            projectsContainer.innerHTML = '';
            const projects = allProjects.length > 0 ? allProjects : (data.recommended_projects || []);
            if (projects.length > 0) {
                projects.forEach((proj, idx) => {
                    const pTitle = typeof proj === 'object' ? (proj.title || proj.name) : proj;
                    const pDiff = typeof proj === 'object' ? (proj.difficulty || (idx === 0 ? 'Beginner' : (idx === 1 ? 'Intermediate' : 'Advanced Portfolio'))) : (idx === 0 ? 'Beginner' : (idx === 1 ? 'Intermediate' : 'Advanced'));
                    const pBuild = typeof proj === 'object' ? (proj.what_to_build || proj.description) : '';
                    const pOut = typeof proj === 'object' ? proj.expected_outcome : '';
                    const pSkills = typeof proj === 'object' ? (proj.skills || []) : [];

                    const pDiv = document.createElement('div');
                    pDiv.style.backgroundColor = 'var(--surface-secondary)';
                    pDiv.style.border = '1px solid var(--border-light)';
                    pDiv.style.borderRadius = 'var(--radius-sm)';
                    pDiv.style.padding = '0.85rem 1rem';

                    pDiv.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem;">
                            <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--dark); margin: 0;">PROJECT ${idx + 1}: ${pTitle}</h4>
                            <span class="badge badge-warning" style="font-size: 0.75rem;">${pDiff.toUpperCase()}</span>
                        </div>
                        ${pSkills.length > 0 ? `<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;"><strong>Skills Applied:</strong> ${pSkills.join(', ')}</div>` : ''}
                        ${pBuild ? `<p style="font-size: 0.84rem; color: var(--dark); margin: 0.4rem 0 0 0; line-height: 1.4;"><strong>What to Build:</strong> ${pBuild}</p>` : ''}
                        ${pOut ? `<p style="font-size: 0.84rem; color: var(--text-secondary); margin: 0.2rem 0 0 0; line-height: 1.4;"><strong>Outcome:</strong> ${pOut}</p>` : ''}
                    `;
                    projectsContainer.appendChild(pDiv);
                });
            } else {
                projectsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.88rem;">Build 2-3 production-ready GitHub repositories demonstrating role skills.</div>';
            }
        }

        // Job-Ready Checklist Container
        if (checklistContainer) {
            checklistContainer.innerHTML = '';
            const checklistItems = [
                "Required technical skills & programming languages mastered",
                "Essential developer tools & container tech configured",
                "2+ Portfolio projects deployed to public GitHub repository",
                "Official industry certification syllabus completed",
                `Resume optimized and tailored for ${comp} ATS standard`,
                "Technical & behavioral mock interview training completed"
            ];

            checklistItems.forEach((item, idx) => {
                const itemDiv = document.createElement('div');
                itemDiv.style.display = 'flex';
                itemDiv.style.alignItems = 'center';
                itemDiv.style.gap = '0.65rem';
                itemDiv.style.backgroundColor = '#FFFFFF';
                itemDiv.style.padding = '0.75rem 1rem';
                itemDiv.style.borderRadius = 'var(--radius-sm)';
                itemDiv.style.border = '1px solid var(--border-light)';

                itemDiv.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" style="flex-shrink: 0;"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    <span style="font-size: 0.88rem; color: var(--dark); font-weight: 500;">${item}</span>
                `;
                checklistContainer.appendChild(itemDiv);
            });
        }

        attachProgressListeners();
    };

    // 5. Attach Interactive Progress Checkbox Handlers
    const attachProgressListeners = () => {
        // Phase level checkboxes
        document.querySelectorAll('.roadmap-phase-checkbox').forEach(cb => {
            cb.addEventListener('change', async (e) => {
                const pIdx = e.target.getAttribute('data-phase');
                const isChecked = e.target.checked;
                await updateProgressOnServer({
                    phase_index: pIdx,
                    item_type: 'phase',
                    status: isChecked ? 'completed' : 'not_started'
                });
            });
        });

        // Skill item level checkboxes
        document.querySelectorAll('.roadmap-item-checkbox').forEach(cb => {
            cb.addEventListener('change', async (e) => {
                const pIdx = e.target.getAttribute('data-phase');
                const iType = e.target.getAttribute('data-type');
                const iIdx = e.target.getAttribute('data-index');
                const isChecked = e.target.checked;
                await updateProgressOnServer({
                    phase_index: pIdx,
                    item_type: iType,
                    item_index: iIdx,
                    status: isChecked ? 'completed' : 'not_started'
                });
            });
        });
    };

    // 6. Update Progress on Server
    const updateProgressOnServer = async (payload) => {
        if (!currentRoadmapId) return;
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-roadmap/${currentRoadmapId}/progress`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                const data = await res.json();
                if (data.progress !== undefined && progressPercentEl && progressBarFillEl) {
                    progressPercentEl.textContent = `${data.progress}%`;
                    progressBarFillEl.style.width = `${data.progress}%`;
                }
                if (data.readiness_score !== undefined && readinessScoreEl) {
                    readinessScoreEl.textContent = `${data.readiness_score}/100`;
                }
            }
        } catch (err) {
            console.error("Failed to update progress:", err);
        }
    };

    // 7. Load Latest Stored Roadmap
    const loadLatestRoadmap = async () => {
        try {
            const token = await getAuthToken();
            if (!token) return;

            const res = await fetch(`${API_BASE_URL}/api/career-roadmap/latest`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data && data.roadmap) {
                    renderRoadmapDetails(data.roadmap);
                }
            }
        } catch (e) {
            console.warn("No active roadmap found:", e);
        }
    };

    // 8. Generate / Refresh Personalized Career Roadmap
    const generateRoadmap = async () => {
        if (!activeCareerGoal && !(await fetchActiveCareerGoal())) {
            showAlert("Please set your Target Company & Job Role in the Career Goal module first.", 'danger');
            return;
        }

        if (btnGenerate) btnGenerate.disabled = true;
        if (btnGenerateText) btnGenerateText.textContent = 'Generating Roadmap...';
        if (loadingStateCard) loadingStateCard.style.display = 'block';
        if (resultsContainer) resultsContainer.style.display = 'none';
        hideAlert();

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-roadmap/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    target_company: activeCareerGoal?.company_name || '',
                    target_role: activeCareerGoal?.job_role || ''
                })
            });

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to generate career roadmap.");
            }

            renderRoadmapDetails(data);
            showAlert("Personalized career roadmap generated successfully.", 'success');
        } catch (err) {
            if (loadingStateCard) loadingStateCard.style.display = 'none';
            showAlert(err.message || "An unexpected error occurred generating your roadmap. Please try again.", 'danger');
        } finally {
            if (btnGenerate) btnGenerate.disabled = false;
            if (btnGenerateText) btnGenerateText.textContent = 'Generate / Refresh Roadmap';
        }
    };

    // 9. Download Roadmap PDF
    const downloadPdf = async () => {
        if (!currentRoadmapId) {
            showAlert("No roadmap available to download. Please generate your roadmap first.", 'danger');
            return;
        }

        if (btnDownloadPdf) {
            btnDownloadPdf.disabled = true;
            btnDownloadPdf.innerHTML = `
                <div class="loading-spinner" style="width: 16px; height: 16px; margin-right: 6px;"></div>
                <span>Generating PDF...</span>
            `;
        }

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-roadmap/${currentRoadmapId}/export-pdf`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!res.ok) {
                throw new Error("Failed to generate roadmap PDF.");
            }

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            const compName = (activeCareerGoal?.company_name || 'Career').replace(/\s+/g, '_');
            const roleName = (activeCareerGoal?.job_role || 'Roadmap').replace(/\s+/g, '_');
            a.download = `CareerPilot_Roadmap_${compName}_${roleName}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err) {
            showAlert(err.message || "Failed to export PDF.", 'danger');
        } finally {
            if (btnDownloadPdf) {
                btnDownloadPdf.disabled = false;
                btnDownloadPdf.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    <span>Download Roadmap as PDF</span>
                `;
            }
        }
    };

    if (btnGenerate) {
        btnGenerate.addEventListener('click', (e) => {
            e.preventDefault();
            generateRoadmap();
        });
    }

    if (btnDownloadPdf) {
        btnDownloadPdf.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdf();
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            await fetchActiveCareerGoal();
            await loadLatestRoadmap();
        }

        supabase.auth.onAuthStateChange(async (event, session) => {
            if (session) {
                await fetchActiveCareerGoal();
                await loadLatestRoadmap();
            }
        });
    };

    init();
});