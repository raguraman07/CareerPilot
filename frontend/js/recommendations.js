// CareerPilot AI — Certification & Project Recommendations Client Module (Phase 7)
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';

const API_BASE_URL = window.API_BASE_URL || 'http://127.0.0.1:5000';

/**
 * Retrieve active user auth token
 */
export async function getAuthToken() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    } catch (err) {
        console.error("Error retrieving auth token for recommendations:", err);
        return null;
    }
}

/**
 * Fetch or generate recommendations
 */
export async function fetchRecommendations(forceRefresh = false) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to access recommendations.");

    const endpoint = forceRefresh ? `${API_BASE_URL}/api/recommendations/generate` : `${API_BASE_URL}/api/recommendations`;
    const method = forceRefresh ? 'POST' : 'GET';

    const response = await fetch(endpoint, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.error || "Failed to load recommendations.");
    }
    return result.data || result;
}

// -------------------------------------------------------------
// Interactive UI Handlers for certifications.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const pageShell = document.getElementById('certifications-page-shell');
    if (!pageShell) return;

    // Header Elements
    const roleTitleEl = document.getElementById('rec-role-title');
    const companyTitleEl = document.getElementById('rec-company-title');
    const summaryTextEl = document.getElementById('rec-summary-text');
    const btnRefresh = document.getElementById('btn-refresh-recommendations');
    const alertBox = document.getElementById('rec-alert-box');

    // Certification Container Elements
    const certsMustList = document.getElementById('certs-must-list');
    const certsRecList = document.getElementById('certs-rec-list');
    const certsAdvList = document.getElementById('certs-adv-list');

    // Project Container Elements
    const projBeginnerList = document.getElementById('proj-beginner-list');
    const projInterList = document.getElementById('proj-inter-list');
    const projAdvList = document.getElementById('proj-adv-list');

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

    const renderCertCard = (cert) => {
        const card = document.createElement('div');
        card.style.cssText = 'background: var(--surface-secondary); border: 1.5px solid var(--border-light); border-radius: var(--radius-md); padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;';
        
        card.innerHTML = `
            <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <span style="font-size: 0.75rem; font-weight: 800; color: var(--primary); text-transform: uppercase;">${escapeHtml(cert.provider || 'Official Provider')}</span>
                    <span class="badge" style="font-size: 0.72rem; background: rgba(82, 70, 70, 0.08);">${escapeHtml(cert.duration || 'Flexible')}</span>
                </div>
                <h4 style="font-size: 1.05rem; font-weight: 800; color: var(--text-primary); margin: 0 0 0.5rem 0;">${escapeHtml(cert.name)}</h4>
                <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.45; margin: 0 0 0.85rem 0;">${escapeHtml(cert.why_useful)}</p>
                <div style="margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 0.35rem;">
                    ${(cert.skills_improved || []).map(s => `<span style="font-size: 0.75rem; background: var(--surface); border: 1px solid var(--border-light); padding: 0.2rem 0.5rem; border-radius: 4px; color: var(--text-primary); font-weight: 600;">${escapeHtml(s)}</span>`).join('')}
                </div>
            </div>
            <div style="border-top: 1px solid var(--border-light); padding-top: 0.75rem; text-align: right;">
                <a href="${escapeHtml(cert.official_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" style="font-size: 0.8rem; font-weight: 700; text-decoration: none; padding: 0.35rem 0.85rem;">
                    View Official Certification ↗
                </a>
            </div>
        `;
        return card;
    };

    const renderProjectCard = (proj) => {
        const card = document.createElement('div');
        card.style.cssText = 'background: var(--surface-secondary); border: 1.5px solid var(--border-light); border-radius: var(--radius-lg); padding: 1.5rem;';

        const techs = proj.technologies || [];
        const features = proj.features || [];

        card.innerHTML = `
            <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 0.75rem; margin-bottom: 0.75rem;">
                <div>
                    <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem;">
                        <span class="badge" style="background: rgba(236, 91, 56, 0.12); color: var(--primary); font-weight: 800; font-size: 0.72rem;">${escapeHtml(proj.difficulty || 'Intermediate').toUpperCase()}</span>
                        <span style="font-size: 0.8rem; color: var(--text-secondary); font-weight: 600;">⏱️ ${escapeHtml(proj.estimated_duration || '2 Weeks')}</span>
                    </div>
                    <h3 style="font-size: 1.2rem; font-weight: 800; color: var(--text-primary); margin: 0;">${escapeHtml(proj.title)}</h3>
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                    ${techs.map(t => `<span style="font-size: 0.78rem; font-weight: 700; background: var(--surface); color: var(--primary); border: 1px solid var(--primary); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm);">${escapeHtml(t)}</span>`).join('')}
                </div>
            </div>

            <p style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5; margin: 0 0 0.85rem 0;">
                <strong>Problem Solved:</strong> ${escapeHtml(proj.real_world_problem)}
            </p>

            <!-- Features -->
            <div style="background: var(--surface); border-radius: var(--radius-sm); padding: 0.85rem 1.25rem; margin-bottom: 1rem; border: 1px solid var(--border-light);">
                <strong style="font-size: 0.85rem; color: var(--text-primary); text-transform: uppercase;">Key Architectural Features:</strong>
                <ul style="padding-left: 1.2rem; margin: 0.4rem 0 0 0; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.45;">
                    ${features.map(f => `<li>${escapeHtml(f)}</li>`).join('')}
                </ul>
            </div>

            <!-- Resume Impact Box -->
            <div style="background: rgba(46, 125, 50, 0.08); border-left: 3.5px solid #2e7d32; padding: 0.75rem 1rem; border-radius: 4px; font-size: 0.85rem; color: var(--text-primary); margin-bottom: 0.85rem;">
                <strong style="color: #2e7d32;">💼 Add to Resume:</strong> "${escapeHtml(proj.resume_impact)}"
            </div>

            <!-- Deployment & Folder Structure Dropdown -->
            <details style="font-size: 0.82rem; color: var(--text-secondary); cursor: pointer;">
                <summary style="font-weight: 700; color: var(--text-primary); margin-bottom: 0.35rem;">📂 View Architecture & Deployment Advice</summary>
                <div style="padding: 0.75rem; background: var(--surface); border-radius: var(--radius-sm); margin-top: 0.35rem; border: 1px solid var(--border-light);">
                    <p style="margin: 0 0 0.5rem 0;"><strong>Deployment:</strong> ${escapeHtml(proj.deployment_suggestion || 'Containerized Cloud Deployment')}</p>
                    <pre style="background: var(--surface-secondary); padding: 0.75rem; border-radius: 4px; overflow-x: auto; font-family: monospace; font-size: 0.8rem; color: var(--text-primary); margin: 0;">${escapeHtml(proj.folder_structure || 'src/\n└── app.py')}</pre>
                </div>
            </details>
        `;
        return card;
    };

    const loadRecommendations = async (forceRefresh = false) => {
        hideAlert();

        // 1. Verify user has set a Career Goal first
        try {
            const goal = await getCurrentCareerGoal();
            if (!goal || !goal.company_name || !goal.job_role) {
                if (roleTitleEl) roleTitleEl.textContent = 'Set Your Target Goal';
                if (companyTitleEl) companyTitleEl.textContent = '';
                if (summaryTextEl) {
                    summaryTextEl.innerHTML = `You haven't set an active career goal yet. <a href="career-goal.html" style="color: var(--primary); font-weight: 700;">Set your target company & role in Step 1</a> and complete your profile to have Gemini AI generate personalized project and certification recommendations.`;
                }
                if (certsMustList) certsMustList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); grid-column: 1 / -1; font-style: italic;">No certifications generated yet. Set your Career Goal first.</div>';
                if (certsRecList) certsRecList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); grid-column: 1 / -1; font-style: italic;">No recommendations available yet.</div>';
                if (certsAdvList) certsAdvList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); grid-column: 1 / -1; font-style: italic;">No advanced credentials available yet.</div>';
                if (projBeginnerList) projBeginnerList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-style: italic;">No beginner projects generated yet.</div>';
                if (projInterList) projInterList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-style: italic;">No intermediate projects generated yet.</div>';
                if (projAdvList) projAdvList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-style: italic;">No advanced projects generated yet.</div>';
                if (btnRefresh) btnRefresh.style.display = 'none';
                return;
            }
        } catch (goalErr) {
            console.warn("Error checking career goal:", goalErr);
        }

        if (btnRefresh) {
            btnRefresh.style.display = 'inline-flex';
            btnRefresh.disabled = true;
            btnRefresh.textContent = "Analyzing & Generating...";
        }

        try {
            const data = await fetchRecommendations(forceRefresh);

            if (roleTitleEl) roleTitleEl.textContent = data.target_role || 'Target Role';
            if (companyTitleEl) companyTitleEl.textContent = data.target_company || 'Target Company';
            if (summaryTextEl && data.career_value_summary) {
                summaryTextEl.textContent = data.career_value_summary;
            }

            const certs = data.certifications || {};
            const projs = data.projects || {};

            // Render Certifications
            if (certsMustList) {
                certsMustList.innerHTML = '';
                const mustCerts = certs.must_complete || [];
                if (mustCerts.length > 0) {
                    mustCerts.forEach(c => certsMustList.appendChild(renderCertCard(c)));
                } else {
                    certsMustList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No mandatory certifications for this specific profile. Focus on projects.</div>';
                }
            }
            if (certsRecList) {
                certsRecList.innerHTML = '';
                const recCerts = certs.recommended || [];
                if (recCerts.length > 0) {
                    recCerts.forEach(c => certsRecList.appendChild(renderCertCard(c)));
                } else {
                    certsRecList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No recommended certifications listed.</div>';
                }
            }
            if (certsAdvList) {
                certsAdvList.innerHTML = '';
                const advCerts = certs.advanced || [];
                if (advCerts.length > 0) {
                    advCerts.forEach(c => certsAdvList.appendChild(renderCertCard(c)));
                } else {
                    certsAdvList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No advanced credentials required at this stage.</div>';
                }
            }

            // Render Projects
            if (projBeginnerList) {
                projBeginnerList.innerHTML = '';
                const begProjs = projs.beginner || [];
                if (begProjs.length > 0) {
                    begProjs.forEach(p => projBeginnerList.appendChild(renderProjectCard(p)));
                } else {
                    projBeginnerList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No beginner projects recommended. Proceed to intermediate portfolio systems.</div>';
                }
            }
            if (projInterList) {
                projInterList.innerHTML = '';
                const interProjs = projs.intermediate || [];
                if (interProjs.length > 0) {
                    interProjs.forEach(p => projInterList.appendChild(renderProjectCard(p)));
                } else {
                    projInterList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No intermediate projects recommended.</div>';
                }
            }
            if (projAdvList) {
                projAdvList.innerHTML = '';
                const advProjs = projs.advanced || [];
                if (advProjs.length > 0) {
                    advProjs.forEach(p => projAdvList.appendChild(renderProjectCard(p)));
                } else {
                    projAdvList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No advanced projects recommended.</div>';
                }
            }

        } catch (err) {
            showAlert(err.message || "Failed to load recommendations.", "danger");
        } finally {
            if (btnRefresh) {
                btnRefresh.disabled = false;
                btnRefresh.textContent = "🔄 Refresh Recommendations";
            }
        }
    };

    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => loadRecommendations(true));
    }

    loadRecommendations();
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
