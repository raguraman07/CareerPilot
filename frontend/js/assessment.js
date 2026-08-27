// CareerPilot AI — Unified Career Analysis Frontend Client Module
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';
import { getCandidateProfile } from './candidateProfile.js';
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
        console.error("Error retrieving auth token for assessment:", err);
        return null;
    }
}

/**
 * Fetch latest uploaded resume from backend
 */
export async function getActiveResumeDoc() {
    try {
        const token = await getAuthToken();
        if (!token) return null;

        const response = await fetch(`${API_BASE_URL}/api/resume/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) return null;
        const list = await response.json();
        return Array.isArray(list) && list.length > 0 ? list[0] : null;
    } catch (err) {
        console.error("Failed to fetch resume doc:", err);
        return null;
    }
}

/**
 * Upload or replace candidate resume
 */
export async function uploadResumeFile(file) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to upload a resume.");

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/resume/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to upload resume.");
    }
    return data;
}

/**
 * Fetch the latest generated Career Assessment
 */
export async function getCurrentAssessment() {
    try {
        const token = await getAuthToken();
        if (!token) return null;

        const response = await fetch(`${API_BASE_URL}/api/assessment/current`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) return null;
        const data = await response.json();
        return data.assessment || null;
    } catch (err) {
        console.error("Failed to fetch current assessment:", err);
        return null;
    }
}

/**
 * Trigger fresh Career Assessment generation
 */
export async function runCareerAssessment(jobDescription = "", forceRefresh = false) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to run a career assessment.");
    }

    const response = await fetch(`${API_BASE_URL}/api/assessment/generate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            job_description: jobDescription,
            force_refresh: forceRefresh
        })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to generate career assessment.");
    }

    return data.assessment;
}

// -------------------------------------------------------------
// Interactive UI Handlers for assessment.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const assessPage = document.getElementById('career-assessment-page');
    if (!assessPage) return;

    // DOM Elements
    const goalCompanyText = document.getElementById('assess-goal-company');
    const goalRoleText = document.getElementById('assess-goal-role');
    const goalExpText = document.getElementById('assess-goal-exp');
    const goalLocationText = document.getElementById('assess-goal-location');
    const noGoalBanner = document.getElementById('assess-no-goal-banner');
    const goalBanner = document.getElementById('assess-goal-banner');

    const btnRun = document.getElementById('btn-run-assessment');
    const btnForceRefresh = document.getElementById('btn-refresh-assessment');
    const alertBox = document.getElementById('assessment-alert-box');

    const resDocFilename = document.getElementById('res-doc-filename');
    const resDocMeta = document.getElementById('res-doc-meta');
    const fileInput = document.getElementById('unified-resume-file');
    const resumeStatus = document.getElementById('active-resume-status');

    const resultsContainer = document.getElementById('assessment-results-container');
    const emptyState = document.getElementById('assessment-empty-state');

    // Result Card Selectors
    const readinessScoreVal = document.getElementById('res-readiness-score');
    const atsScoreVal = document.getElementById('res-ats-score');
    const summaryText = document.getElementById('res-summary-text');
    const priorityActionsList = document.getElementById('res-priority-actions-list');
    const strongSkillsContainer = document.getElementById('res-strong-skills-list');
    const partialSkillsContainer = document.getElementById('res-partial-skills-list');
    const skillGapsTableBody = document.getElementById('res-skill-gaps-tbody');
    const progLanguagesContainer = document.getElementById('res-prog-languages-list');
    const knowledgeGapsContainer = document.getElementById('res-knowledge-gaps-list');
    const certRelevanceContainer = document.getElementById('res-cert-relevance-list');
    const projectStrengthsText = document.getElementById('res-project-strengths');
    const recommendedProjectsList = document.getElementById('res-recommended-projects-list');
    const resumeGapsList = document.getElementById('res-resume-gaps-list');

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
        } else {
            alertBox.style.background = 'rgba(82, 70, 70, 0.08)';
            alertBox.style.color = '#524646';
            alertBox.style.border = '1px solid var(--border)';
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // Load active resume details
    const loadResumeInfo = async () => {
        try {
            const doc = await getActiveResumeDoc();
            if (doc) {
                if (resDocFilename) resDocFilename.textContent = doc.filename || 'Active Resume';
                if (resDocMeta) {
                    resDocMeta.textContent = `Uploaded: ${doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'Recently'} • ${doc.pages || 1} Page(s)`;
                }
                if (resumeStatus) resumeStatus.textContent = '✓ Resume Active';
            } else {
                if (resDocFilename) resDocFilename.textContent = 'No resume uploaded yet';
                if (resDocMeta) resDocMeta.textContent = 'Upload PDF or DOCX to run target role matching';
                if (resumeStatus) resumeStatus.textContent = '';
            }
        } catch (e) {
            console.error("Resume info error:", e);
        }
    };

    // Upload Resume Handler
    if (fileInput) {
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            hideAlert();
            if (resumeStatus) resumeStatus.textContent = 'Uploading & Extracting...';

            try {
                await uploadResumeFile(file);
                showAlert("Resume uploaded and parsed successfully! Running fresh Career Analysis...", "success");
                await loadResumeInfo();
                await handleRunAssessment(true);
            } catch (err) {
                showAlert(err.message || "Failed to upload resume.", "danger");
                if (resumeStatus) resumeStatus.textContent = '';
            }
        });
    }

    const renderAssessmentData = (assessment) => {
        if (!assessment) {
            if (resultsContainer) resultsContainer.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        // 1. Scores & Overview
        if (readinessScoreVal) readinessScoreVal.textContent = `${assessment.career_readiness_score || 0}%`;
        if (atsScoreVal) atsScoreVal.textContent = `${assessment.ats_score || 0}%`;
        if (summaryText) summaryText.textContent = assessment.summary || "Career readiness assessment prepared.";

        // 2. Priority Actions
        if (priorityActionsList) {
            priorityActionsList.innerHTML = '';
            (assessment.priority_actions || []).forEach(act => {
                const li = document.createElement('li');
                li.style.cssText = 'margin-bottom: 0.6rem; font-size: 0.95rem; color: var(--text-primary); line-height: 1.5;';
                li.textContent = act;
                priorityActionsList.appendChild(li);
            });
        }

        // 3. Strengths & Partial
        if (strongSkillsContainer) {
            strongSkillsContainer.innerHTML = '';
            (assessment.strong_matches || []).forEach(sk => {
                const pill = document.createElement('span');
                pill.style.cssText = 'display: inline-block; padding: 0.35rem 0.85rem; background: rgba(46, 125, 50, 0.12); color: #2e7d32; border: 1px solid rgba(46, 125, 50, 0.3); border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 600;';
                pill.textContent = `✓ ${sk}`;
                strongSkillsContainer.appendChild(pill);
            });
            if (!assessment.strong_matches || assessment.strong_matches.length === 0) {
                strongSkillsContainer.innerHTML = '<span style="color:var(--text-secondary); font-size:0.88rem; font-style:italic;">Add more details in your profile or resume to identify strengths.</span>';
            }
        }

        if (partialSkillsContainer) {
            partialSkillsContainer.innerHTML = '';
            (assessment.partial_matches || []).forEach(sk => {
                const pill = document.createElement('span');
                pill.style.cssText = 'display: inline-block; padding: 0.35rem 0.85rem; background: rgba(230, 81, 0, 0.12); color: #e65100; border: 1px solid rgba(230, 81, 0, 0.3); border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 600;';
                pill.textContent = `⚡ ${sk}`;
                partialSkillsContainer.appendChild(pill);
            });
            if (!assessment.partial_matches || assessment.partial_matches.length === 0) {
                partialSkillsContainer.innerHTML = '<span style="color:var(--text-secondary); font-size:0.88rem; font-style:italic;">No intermediate partial skills identified.</span>';
            }
        }

        // 4. Missing Skills & Gaps Table
        if (skillGapsTableBody) {
            skillGapsTableBody.innerHTML = '';
            (assessment.skill_gaps || []).forEach(gap => {
                const tr = document.createElement('tr');
                const pColor = gap.priority === 'HIGH' ? '#c62828' : (gap.priority === 'MEDIUM' ? '#e65100' : '#2e7d32');
                const pBg = gap.priority === 'HIGH' ? 'rgba(198,40,40,0.1)' : (gap.priority === 'MEDIUM' ? 'rgba(230,81,0,0.1)' : 'rgba(46,125,50,0.1)');
                
                tr.innerHTML = `
                    <td style="padding: 1rem; border-bottom: 1px solid var(--border-light); font-weight: 700; color: var(--text-primary);">
                        ${escapeHtml(gap.skill)}
                        <span style="display:block; font-size:0.75rem; font-weight:500; color:var(--text-secondary); text-transform:capitalize;">${escapeHtml(gap.category || 'Technical')}</span>
                    </td>
                    <td style="padding: 1rem; border-bottom: 1px solid var(--border-light);">
                        <span style="display:inline-block; padding: 0.2rem 0.55rem; background:${pBg}; color:${pColor}; border-radius:4px; font-weight:700; font-size:0.78rem;">${escapeHtml(gap.priority || 'MEDIUM')}</span>
                    </td>
                    <td style="padding: 1rem; border-bottom: 1px solid var(--border-light); font-size: 0.9rem; color: var(--text-primary);">
                        <strong>Why:</strong> ${escapeHtml(gap.why || '')}<br/>
                        ${gap.what_to_learn && gap.what_to_learn.length > 0 ? `<strong style="display:inline-block; margin-top:0.3rem;">Learn:</strong> ${escapeHtml(gap.what_to_learn.join(', '))}` : ''}
                    </td>
                    <td style="padding: 1rem; border-bottom: 1px solid var(--border-light); font-size: 0.88rem; color: var(--text-secondary);">
                        ${escapeHtml(gap.practice_task || 'Practice mini-task.')}
                    </td>
                `;
                skillGapsTableBody.appendChild(tr);
            });
        }

        // 5. Programming Languages
        if (progLanguagesContainer) {
            progLanguagesContainer.innerHTML = '';
            (assessment.programming_language_gaps || []).forEach(pl => {
                const card = document.createElement('div');
                card.style.cssText = 'background: var(--surface-secondary); padding: 0.85rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-light);';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
                        <strong style="color:var(--text-primary); font-size:0.95rem;">${escapeHtml(pl.language)}</strong>
                        <span style="font-size:0.78rem; font-weight:600; color:var(--primary);">${escapeHtml(pl.status)}</span>
                    </div>
                    <p style="font-size:0.84rem; color:var(--text-secondary); margin:0;">${escapeHtml(pl.recommendation || '')}</p>
                `;
                progLanguagesContainer.appendChild(card);
            });
        }

        // 6. Knowledge Gaps
        if (knowledgeGapsContainer) {
            knowledgeGapsContainer.innerHTML = '';
            (assessment.knowledge_gaps || []).forEach(kg => {
                const item = document.createElement('div');
                item.style.cssText = 'background: var(--surface-secondary); padding: 0.85rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-light);';
                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem;">
                        <strong style="color:var(--text-primary); font-size:0.95rem;">${escapeHtml(kg.topic)}</strong>
                        <span style="font-size:0.75rem; font-weight:700; color:var(--danger);">${escapeHtml(kg.priority || 'HIGH')} PRIORITY</span>
                    </div>
                    <p style="font-size:0.84rem; color:var(--text-secondary); margin:0;">${escapeHtml(kg.relevance || '')}</p>
                `;
                knowledgeGapsContainer.appendChild(item);
            });
        }

        // 7. Certifications
        if (certRelevanceContainer) {
            certRelevanceContainer.innerHTML = '';
            (assessment.certification_relevance || []).forEach(cr => {
                const item = document.createElement('div');
                item.style.cssText = 'background: var(--surface-secondary); padding: 0.85rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-light);';
                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem;">
                        <strong style="color:var(--text-primary); font-size:0.95rem;">${escapeHtml(cr.name)}</strong>
                        <span style="font-size:0.78rem; font-weight:600; color:var(--primary);">${escapeHtml(cr.type || 'Recommended')}</span>
                    </div>
                    <p style="font-size:0.84rem; color:var(--text-secondary); margin:0;">${escapeHtml(cr.reason || '')}</p>
                `;
                certRelevanceContainer.appendChild(item);
            });
        }

        // 8. Projects
        const pGaps = assessment.project_gaps || {};
        if (projectStrengthsText) {
            projectStrengthsText.textContent = (pGaps.existing_strengths && pGaps.existing_strengths.length > 0)
                ? pGaps.existing_strengths.join('. ')
                : "Add practical projects in your Profile to strengthen evidence for this role.";
        }
        if (recommendedProjectsList) {
            recommendedProjectsList.innerHTML = '';
            (pGaps.recommended_projects || []).forEach(rp => {
                const pEl = document.createElement('div');
                pEl.style.cssText = 'background: var(--surface-secondary); padding: 1rem; border-radius: var(--radius-md); border-left: 3px solid var(--primary); margin-bottom: 0.75rem;';
                pEl.innerHTML = `
                    <h4 style="font-size:1rem; font-weight:700; color:var(--text-primary); margin-bottom:0.25rem;">${escapeHtml(rp.title)}</h4>
                    <p style="font-size:0.88rem; color:var(--text-primary); margin-bottom:0.35rem;">${escapeHtml(rp.description)}</p>
                    <p style="font-size:0.82rem; color:var(--text-secondary); font-style:italic; margin:0;"><strong>Why:</strong> ${escapeHtml(rp.why)}</p>
                `;
                recommendedProjectsList.appendChild(pEl);
            });
        }

        // 9. Resume Gaps
        if (resumeGapsList) {
            resumeGapsList.innerHTML = '';
            (assessment.resume_gaps || []).forEach(rg => {
                const li = document.createElement('li');
                li.style.cssText = 'margin-bottom: 0.5rem; font-size: 0.9rem; color: var(--text-primary);';
                li.textContent = rg;
                resumeGapsList.appendChild(li);
            });
        }
    };

    const handleRunAssessment = async (forceRefresh = false) => {
        hideAlert();
        if (btnRun) {
            btnRun.disabled = true;
            btnRun.querySelector('.btn-text').textContent = 'Analyzing Target Role...';
        }
        if (btnForceRefresh) btnForceRefresh.disabled = true;

        try {
            const assessment = await runCareerAssessment("", forceRefresh);
            renderAssessmentData(assessment);
            showAlert("Career Analysis successfully updated!", "success");
        } catch (err) {
            showAlert(err.message || "Failed to generate Career Analysis.", "danger");
        } finally {
            if (btnRun) {
                btnRun.disabled = false;
                btnRun.querySelector('.btn-text').textContent = '🚀 Run Complete Career Analysis';
            }
            if (btnForceRefresh) btnForceRefresh.disabled = false;
        }
    };

    // Load Initial Data
    try {
        const goal = await getCurrentCareerGoal();
        if (goal) {
            if (goalBanner) goalBanner.style.display = 'flex';
            if (noGoalBanner) noGoalBanner.style.display = 'none';
            if (goalCompanyText) goalCompanyText.textContent = goal.company_name || 'Target Company';
            if (goalRoleText) goalRoleText.textContent = goal.job_role || 'Target Role';
            if (goalExpText) goalExpText.textContent = goal.experience_level || 'Fresher';
            if (goalLocationText) goalLocationText.textContent = goal.target_location || 'Flexible';
        } else {
            if (goalBanner) goalBanner.style.display = 'none';
            if (noGoalBanner) noGoalBanner.style.display = 'block';
        }

        await loadResumeInfo();

        const currentAssessment = await getCurrentAssessment();
        if (currentAssessment) {
            renderAssessmentData(currentAssessment);
        } else {
            renderAssessmentData(null);
        }
    } catch (err) {
        console.error("Initialization error:", err);
    }

    if (btnRun) {
        btnRun.addEventListener('click', () => handleRunAssessment(false));
    }
    if (btnForceRefresh) {
        btnForceRefresh.addEventListener('click', () => handleRunAssessment(true));
    }
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
