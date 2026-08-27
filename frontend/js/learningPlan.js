// CareerPilot AI — Personalized Learning Path & Skill Development Client Module (Phase 4)
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';
import { getCurrentAssessment } from './assessment.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:5000'
    : 'https://careerpilot-txa0.onrender.com';

/**
 * Retrieve active user auth token
 */
export async function getAuthToken() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    } catch (err) {
        console.error("Error retrieving auth token for learning plan:", err);
        return null;
    }
}

/**
 * Fetch the authenticated user's current active Learning Plan
 */
export async function getCurrentLearningPlan() {
    try {
        const token = await getAuthToken();
        if (!token) return null;

        const response = await fetch(`${API_BASE_URL}/api/learning-plan/current`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) return null;
        const data = await response.json();
        return data.learning_plan || null;
    } catch (err) {
        console.error("Failed to fetch current learning plan:", err);
        return null;
    }
}

/**
 * Generate or refresh the user's Personalized Learning Plan
 */
export async function generateLearningPlan(forceRefresh = false, timeline = null) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to generate a learning plan.");
    }

    const payload = { force_refresh: forceRefresh };
    if (timeline) payload.timeline = timeline;

    const response = await fetch(`${API_BASE_URL}/api/learning-plan/generate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to generate learning plan.");
    }

    return data.learning_plan;
}

/**
 * Update the learning progress for a specific skill item
 * Statuses: NOT_STARTED, IN_PROGRESS, COMPLETED, VERIFIED
 */
export async function updateSkillProgress(skillId, newStatus, planId = null) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to update progress.");
    }

    const response = await fetch(`${API_BASE_URL}/api/learning-plan/progress`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            skill_id: skillId,
            status: newStatus,
            plan_id: planId
        })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to update skill progress.");
    }

    return data;
}

// -------------------------------------------------------------
// Interactive UI Handlers for learning-plan.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const planPage = document.getElementById('career-learning-plan-page');
    if (!planPage) return;

    // Prerequisite & Header DOM Elements
    const goalBanner = document.getElementById('plan-goal-banner');
    const noGoalBanner = document.getElementById('plan-no-goal-banner');
    const noAssessBanner = document.getElementById('plan-no-assess-banner');
    
    const goalCompanyText = document.getElementById('plan-goal-company');
    const goalRoleText = document.getElementById('plan-goal-role');
    const goalExpText = document.getElementById('plan-goal-exp');
    const goalTimelineText = document.getElementById('plan-goal-timeline');
    const assessScoreBadge = document.getElementById('plan-readiness-badge');

    // Progress Dashboard DOM Elements
    const overallProgressVal = document.getElementById('plan-overall-progress-val');
    const overallProgressBar = document.getElementById('plan-overall-progress-bar');
    const countTotalSkills = document.getElementById('plan-count-total');
    const countInProgress = document.getElementById('plan-count-in-progress');
    const countCompleted = document.getElementById('plan-count-completed');
    const countVerified = document.getElementById('plan-count-verified');

    // Plan Content DOM Elements
    const emptyState = document.getElementById('plan-empty-state');
    const resultsContainer = document.getElementById('plan-results-container');
    const planSummaryText = document.getElementById('plan-summary-text');
    const phasesContainer = document.getElementById('plan-phases-timeline');
    const alertBox = document.getElementById('plan-alert-box');

    // Controls
    const btnGenerate = document.getElementById('btn-generate-plan');
    const btnRefreshPlan = document.getElementById('btn-refresh-plan');
    const filterButtons = document.querySelectorAll('.plan-filter-btn');

    let currentActivePlan = null;
    let activeFilter = 'ALL';

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
        }
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // Calculate Summary Stats from Active Plan
    const updateDashboardCounters = (plan) => {
        if (!plan || !plan.phases) return;

        let total = 0;
        let inProg = 0;
        let completed = 0;
        let verified = 0;

        plan.phases.forEach(phase => {
            (phase.skills || []).forEach(sk => {
                total++;
                if (sk.status === 'IN_PROGRESS') inProg++;
                else if (sk.status === 'COMPLETED') completed++;
                else if (sk.status === 'VERIFIED') verified++;
            });
        });

        const progressPercent = total > 0 ? Math.round(((completed + verified) / total) * 100) : 0;
        
        if (overallProgressVal) overallProgressVal.textContent = `${progressPercent}%`;
        if (overallProgressBar) overallProgressBar.style.width = `${progressPercent}%`;
        if (countTotalSkills) countTotalSkills.textContent = total;
        if (countInProgress) countInProgress.textContent = inProg;
        if (countCompleted) countCompleted.textContent = completed;
        if (countVerified) countVerified.textContent = verified;
    };

    // Render Phases and Skills
    const renderPlan = (plan) => {
        if (!plan || !plan.phases || plan.phases.length === 0) {
            if (resultsContainer) resultsContainer.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        currentActivePlan = plan;
        if (emptyState) emptyState.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        if (planSummaryText) {
            planSummaryText.textContent = plan.plan_summary || "Here is your structured personalized learning plan.";
        }

        updateDashboardCounters(plan);

        if (!phasesContainer) return;
        phasesContainer.innerHTML = '';

        plan.phases.forEach((phase, phaseIdx) => {
            const phaseWrapper = document.createElement('div');
            phaseWrapper.className = 'plan-phase-block';
            phaseWrapper.style.cssText = 'background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--shadow-sm);';

            const phaseHeader = document.createElement('div');
            phaseHeader.style.cssText = 'display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; border-bottom: 1px solid var(--border-light); padding-bottom: 1rem;';
            
            phaseHeader.innerHTML = `
                <div>
                    <span style="font-size: 0.78rem; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 0.05em;">Phase ${phase.order || phaseIdx + 1}</span>
                    <h3 style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary); margin: 0.2rem 0 0.4rem 0;">${escapeHtml(phase.name)}</h3>
                    <p style="font-size: 0.88rem; color: var(--text-secondary); margin: 0;">${escapeHtml(phase.description || '')}</p>
                </div>
                <span class="badge" style="background: rgba(82, 70, 70, 0.08); color: var(--text-primary); font-weight: 700; padding: 0.35rem 0.75rem; border-radius: var(--radius-full); font-size: 0.8rem;">
                    ${(phase.skills || []).length} ${(phase.skills || []).length === 1 ? 'Skill' : 'Skills'}
                </span>
            `;
            phaseWrapper.appendChild(phaseHeader);

            const skillsGrid = document.createElement('div');
            skillsGrid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem;';

            let visibleSkillsCount = 0;

            (phase.skills || []).forEach(sk => {
                // Apply Active Filter
                if (activeFilter === 'HIGH' && sk.priority !== 'HIGH') return;
                if (activeFilter === 'IN_PROGRESS' && sk.status !== 'IN_PROGRESS') return;
                if (activeFilter === 'COMPLETED' && !['COMPLETED', 'VERIFIED'].includes(sk.status)) return;
                if (activeFilter === 'NOT_STARTED' && sk.status !== 'NOT_STARTED') return;

                visibleSkillsCount++;

                const skCard = document.createElement('div');
                skCard.className = 'plan-skill-card';
                skCard.id = `card-${sk.skill_id}`;
                
                // Colors based on priority & status
                const pColor = sk.priority === 'HIGH' ? '#c62828' : (sk.priority === 'MEDIUM' ? '#e65100' : '#2e7d32');
                const pBg = sk.priority === 'HIGH' ? 'rgba(198,40,40,0.1)' : (sk.priority === 'MEDIUM' ? 'rgba(230,81,0,0.1)' : 'rgba(46,125,50,0.1)');
                
                let statusBadgeBg = 'rgba(168, 164, 146, 0.15)';
                let statusBadgeColor = 'var(--text-secondary)';
                let statusText = 'NOT STARTED';

                if (sk.status === 'IN_PROGRESS') {
                    statusBadgeBg = 'rgba(236, 91, 56, 0.15)';
                    statusBadgeColor = '#EC5B38';
                    statusText = 'IN PROGRESS';
                } else if (sk.status === 'COMPLETED') {
                    statusBadgeBg = 'rgba(46, 125, 50, 0.15)';
                    statusBadgeColor = '#2e7d32';
                    statusText = 'COMPLETED';
                } else if (sk.status === 'VERIFIED') {
                    statusBadgeBg = 'rgba(2, 119, 189, 0.15)';
                    statusBadgeColor = '#0277bd';
                    statusText = 'VERIFIED';
                }

                skCard.style.cssText = `background: var(--surface-secondary); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; border-left: 4px solid ${pColor};`;

                // Topics list items
                const topicsHtml = (sk.topics || []).map(t => `<li style="font-size: 0.85rem; color: var(--text-primary); margin-bottom: 0.25rem;">✓ ${escapeHtml(t)}</li>`).join('');

                // Practice tasks
                const practiceHtml = (sk.practice_tasks || []).map(pt => `<div style="background: var(--surface); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); border: 1px dashed var(--border-light); font-size: 0.84rem; color: var(--text-primary); margin-top: 0.35rem;">🛠️ ${escapeHtml(pt)}</div>`).join('');

                skCard.innerHTML = `
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-size: 0.75rem; font-weight: 700; color: ${pColor}; background: ${pBg}; padding: 0.2rem 0.55rem; border-radius: 4px;">
                                ${escapeHtml(sk.priority)} PRIORITY
                            </span>
                            <span id="status-badge-${sk.skill_id}" style="font-size: 0.75rem; font-weight: 700; color: ${statusBadgeColor}; background: ${statusBadgeBg}; padding: 0.2rem 0.55rem; border-radius: 4px;">
                                ${statusText}
                            </span>
                        </div>

                        <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.25rem 0;">${escapeHtml(sk.name)}</h4>
                        <div style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
                            <span>${escapeHtml(sk.category || 'Technical')}</span> • <span>Effort: ${escapeHtml(sk.estimated_effort || '1-2 Weeks')}</span>
                        </div>

                        <div style="display: flex; gap: 0.5rem; align-items: center; font-size: 0.8rem; background: var(--surface); padding: 0.4rem 0.6rem; border-radius: var(--radius-sm); margin-bottom: 0.75rem;">
                            <span style="color: var(--text-secondary);">Level:</span>
                            <strong style="color: var(--text-primary);">${escapeHtml(sk.current_level || 'NOT_STARTED')}</strong>
                            <span style="color: var(--primary);">➔</span>
                            <strong style="color: var(--primary);">${escapeHtml(sk.target_level || 'INTERMEDIATE')}</strong>
                        </div>

                        <div style="margin-bottom: 0.75rem;">
                            <strong style="font-size: 0.82rem; color: var(--text-primary); text-transform: uppercase;">Why You Need It:</strong>
                            <p style="font-size: 0.86rem; color: var(--text-primary); line-height: 1.45; margin: 0.2rem 0 0 0;">${escapeHtml(sk.why_needed || '')}</p>
                        </div>

                        ${sk.topics && sk.topics.length > 0 ? `
                        <div style="margin-bottom: 0.75rem;">
                            <strong style="font-size: 0.82rem; color: var(--text-primary); text-transform: uppercase;">What to Learn:</strong>
                            <ul style="list-style: none; padding-left: 0; margin: 0.3rem 0 0 0;">${topicsHtml}</ul>
                        </div>` : ''}

                        ${sk.practice_tasks && sk.practice_tasks.length > 0 ? `
                        <div style="margin-bottom: 0.75rem;">
                            <strong style="font-size: 0.82rem; color: var(--text-primary); text-transform: uppercase;">Practice Task:</strong>
                            ${practiceHtml}
                        </div>` : ''}

                        ${sk.expected_outcome ? `
                        <div style="margin-bottom: 1rem;">
                            <strong style="font-size: 0.82rem; color: var(--text-secondary); text-transform: uppercase;">Expected Outcome:</strong>
                            <p style="font-size: 0.83rem; color: var(--text-secondary); font-style: italic; margin: 0.2rem 0 0 0;">${escapeHtml(sk.expected_outcome)}</p>
                        </div>` : ''}
                    </div>

                    <div style="border-top: 1px solid var(--border-light); padding-top: 0.85rem; display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: space-between; align-items: center;">
                        <div style="display: flex; gap: 0.4rem;">
                            <button class="btn btn-sm btn-status-toggle" data-skill-id="${sk.skill_id}" data-action="IN_PROGRESS" style="font-size: 0.75rem; padding: 0.35rem 0.65rem; background: var(--surface); color: var(--primary); border: 1px solid var(--primary); border-radius: var(--radius-sm); cursor: pointer;">
                                In Progress
                            </button>
                            <button class="btn btn-sm btn-status-toggle" data-skill-id="${sk.skill_id}" data-action="COMPLETED" style="font-size: 0.75rem; padding: 0.35rem 0.65rem; background: #2e7d32; color: #ffffff; border: none; border-radius: var(--radius-sm); cursor: pointer;">
                                Mark Completed
                            </button>
                        </div>
                        <a href="knowledge-assessment.html?skill_id=${encodeURIComponent(sk.skill_id)}&skill_name=${encodeURIComponent(sk.name)}" class="btn btn-sm" style="font-size: 0.78rem; font-weight: 700; background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary); padding: 0.35rem 0.75rem; border-radius: var(--radius-sm); text-decoration: none;">
                            Take Assessment ➔
                        </a>
                    </div>
                `;

                skillsGrid.appendChild(skCard);
            });

            if (visibleSkillsCount > 0) {
                phaseWrapper.appendChild(skillsGrid);
                phasesContainer.appendChild(phaseWrapper);
            }
        });

        // If filtering produced no results in any phase
        if (phasesContainer.children.length === 0) {
            phasesContainer.innerHTML = `
                <div style="text-align: center; padding: 2rem; background: var(--surface); border-radius: var(--radius-md); border: 1px dashed var(--border);">
                    <p style="color: var(--text-secondary); margin: 0;">No skills match the selected filter "<strong>${escapeHtml(activeFilter)}</strong>".</p>
                </div>
            `;
        }

        // Attach dynamic event listeners to status toggle buttons
        document.querySelectorAll('.btn-status-toggle').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const skillId = btn.getAttribute('data-skill-id');
                const nextStatus = btn.getAttribute('data-action');
                await handleProgressUpdate(skillId, nextStatus);
            });
        });
    };

    // Update Progress Handler
    const handleProgressUpdate = async (skillId, nextStatus) => {
        try {
            const planId = currentActivePlan ? currentActivePlan.id : null;
            const res = await updateSkillProgress(skillId, nextStatus, planId);
            
            // Mutate local state
            if (currentActivePlan && res.learning_plan) {
                currentActivePlan = res.learning_plan;
                renderPlan(currentActivePlan);
            }
            showAlert(`Skill updated to ${nextStatus.replace('_', ' ')}!`, "success");
        } catch (err) {
            showAlert(err.message || "Failed to update progress.", "danger");
        }
    };

    // Filter Buttons Handler
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter') || 'ALL';
            if (currentActivePlan) {
                renderPlan(currentActivePlan);
            }
        });
    });

    // ---------------------------------------------------------
    // Initial Load: Goal, Assessment, and Stored Learning Plan
    // ---------------------------------------------------------
    try {
        const goal = await getCurrentCareerGoal();
        const assess = await getCurrentAssessment();

        if (!goal) {
            if (goalBanner) goalBanner.style.display = 'none';
            if (noGoalBanner) noGoalBanner.style.display = 'block';
            if (btnGenerate) btnGenerate.disabled = true;
            return;
        }

        if (goalBanner) goalBanner.style.display = 'block';
        if (noGoalBanner) noGoalBanner.style.display = 'none';
        if (goalCompanyText) goalCompanyText.textContent = goal.company_name;
        if (goalRoleText) goalRoleText.textContent = goal.job_role;
        if (goalExpText) goalExpText.textContent = goal.experience_level;
        if (goalTimelineText) goalTimelineText.textContent = goal.target_timeline || '6 Months';

        if (!assess) {
            if (noAssessBanner) noAssessBanner.style.display = 'block';
            if (btnGenerate) btnGenerate.disabled = true;
            return;
        }

        if (noAssessBanner) noAssessBanner.style.display = 'none';
        if (assessScoreBadge) {
            assessScoreBadge.textContent = `${assess.career_readiness_score || 0}% READINESS`;
        }
        if (btnGenerate) btnGenerate.disabled = false;

        // Fetch stored plan
        const plan = await getCurrentLearningPlan();
        if (plan) {
            renderPlan(plan);
        } else {
            renderPlan(null);
        }
    } catch (loadErr) {
        console.error("Error loading learning plan context:", loadErr);
    }

    // ---------------------------------------------------------
    // Generate / Re-generate Plan Handler
    // ---------------------------------------------------------
    const handleGenerate = async (forceRefresh = false) => {
        hideAlert();
        const activeBtn = forceRefresh ? btnRefreshPlan : btnGenerate;
        if (activeBtn) {
            activeBtn.disabled = true;
            activeBtn.classList.add('loading');
            const textSpan = activeBtn.querySelector('.btn-text');
            if (textSpan) textSpan.textContent = "Analyzing Skill Gaps & Building Plan...";
        }

        try {
            const plan = await generateLearningPlan(forceRefresh);
            renderPlan(plan);
            showAlert("Personalized Learning Plan generated successfully!", "success");
            window.scrollTo({ top: 350, behavior: 'smooth' });
        } catch (err) {
            showAlert(err.message || "Failed to generate learning plan.", "danger");
        } finally {
            if (activeBtn) {
                activeBtn.disabled = false;
                activeBtn.classList.remove('loading');
                const textSpan = activeBtn.querySelector('.btn-text');
                if (textSpan) textSpan.textContent = forceRefresh ? "Regenerate Plan" : "Create My Learning Plan";
            }
        }
    };

    if (btnGenerate) {
        btnGenerate.addEventListener('click', (e) => {
            e.preventDefault();
            handleGenerate(false);
        });
    }

    if (btnRefreshPlan) {
        btnRefreshPlan.addEventListener('click', (e) => {
            e.preventDefault();
            handleGenerate(true);
        });
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
