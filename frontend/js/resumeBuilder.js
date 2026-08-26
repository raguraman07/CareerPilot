// CareerPilot AI — Resume Builder & Target Job Optimizer Client Module (Phase 8)
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

/**
 * Retrieve active user auth token
 */
export async function getAuthToken() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    } catch (err) {
        console.error("Error retrieving auth token for resume builder:", err);
        return null;
    }
}

/**
 * Fetch or compile targeted resume
 */
export async function fetchActiveResume(forceRecompile = false) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to access the resume builder.");

    const endpoint = forceRecompile 
        ? `${API_BASE_URL}/api/resume-builder/generate-targeted`
        : `${API_BASE_URL}/api/resume-builder/active`;
    const method = forceRecompile ? 'POST' : 'GET';

    const response = await fetch(endpoint, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.error || "Failed to load resume.");
    }
    return result.resume || result;
}

/**
 * Save resume changes
 */
export async function saveResume(resumeData) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in.");

    const response = await fetch(`${API_BASE_URL}/api/resume-builder/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(resumeData)
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.error || "Failed to save resume.");
    }
    return result.resume;
}

/**
 * AI rewrite a specific section/bullet point
 */
export async function rewriteSection(sectionType, content, targetRole, targetCompany) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in.");

    const response = await fetch(`${API_BASE_URL}/api/resume-builder/rewrite-section`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            section_type: sectionType,
            content: content,
            target_role: targetRole,
            target_company: targetCompany
        })
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.error || "Failed to rewrite content.");
    }
    return result.improved;
}

// -------------------------------------------------------------
// Interactive UI Handlers for resume-builder.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const pageShell = document.getElementById('resume-builder-page-shell');
    if (!pageShell) return;

    // Header Elements
    const roleTitleEl = document.getElementById('builder-role-title');
    const companyTitleEl = document.getElementById('builder-company-title');
    const atsScoreEl = document.getElementById('builder-ats-score');
    const roleAlignmentEl = document.getElementById('builder-role-alignment');
    const completenessEl = document.getElementById('builder-completeness');
    const alertBox = document.getElementById('builder-alert-box');

    // Editor Form Inputs
    const inpFullName = document.getElementById('inp-full-name');
    const inpEmail = document.getElementById('inp-email');
    const inpPhone = document.getElementById('inp-phone');
    const inpSummary = document.getElementById('inp-summary');
    const inpCoreSkills = document.getElementById('inp-core-skills');

    // Controls
    const btnSave = document.getElementById('btn-save-resume');
    const btnPrint = document.getElementById('btn-print-resume');
    const btnRecompile = document.getElementById('btn-recompile-targeted');
    const btnRewriteSummary = document.getElementById('btn-rewrite-summary');

    // Live Paper Preview Elements
    const prevName = document.getElementById('preview-name');
    const prevContacts = document.getElementById('preview-contacts');
    const prevSummary = document.getElementById('preview-summary');
    const prevCoreSkills = document.getElementById('preview-core-skills');
    const prevSupportingSkills = document.getElementById('preview-supporting-skills');
    const prevProjectsList = document.getElementById('preview-projects-list');
    const prevEducationList = document.getElementById('preview-education-list');
    const prevCertsList = document.getElementById('preview-certs-list');

    let currentResume = null;

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

    const syncPreview = () => {
        if (!currentResume) return;

        if (prevName) prevName.textContent = inpFullName.value || 'Candidate Name';
        if (prevContacts) {
            prevContacts.textContent = `${inpEmail.value || 'email@example.com'} | ${inpPhone.value || 'phone'} | ${currentResume.personal_info?.location || 'USA'}`;
        }
        if (prevSummary) prevSummary.textContent = inpSummary.value || 'Professional summary...';

        const coreArray = inpCoreSkills.value.split(',').map(s => s.trim()).filter(Boolean);
        if (prevCoreSkills) prevCoreSkills.textContent = coreArray.join(', ') || 'None';
        if (prevSupportingSkills) {
            prevSupportingSkills.textContent = (currentResume.technical_skills?.supporting || []).join(', ') || 'None';
        }

        // Projects
        if (prevProjectsList) {
            prevProjectsList.innerHTML = '';
            (currentResume.projects || []).forEach(p => {
                const div = document.createElement('div');
                div.style.marginBottom = '0.75rem';
                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; font-size: 0.88rem; font-weight: 700;">
                        <span>${escapeHtml(p.title)}</span>
                        <span style="font-size: 0.8rem; color: #718096;">${escapeHtml((p.technologies || []).join(', '))}</span>
                    </div>
                    <ul style="padding-left: 1.2rem; margin: 0.25rem 0 0 0; font-size: 0.82rem; color: #4a5568; line-height: 1.45;">
                        ${(p.bullets || []).map(b => `<li>${escapeHtml(b)}</li>`).join('')}
                    </ul>
                `;
                prevProjectsList.appendChild(div);
            });
        }

        // Education
        if (prevEducationList) {
            prevEducationList.innerHTML = '';
            (currentResume.education || []).forEach(edu => {
                const div = document.createElement('div');
                div.style.marginBottom = '0.5rem';
                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 700;">
                        <span>${escapeHtml(edu.degree)} — ${escapeHtml(edu.institution)}</span>
                        <span style="font-size: 0.8rem; color: #718096;">${escapeHtml(edu.graduation_year || '')}</span>
                    </div>
                `;
                prevEducationList.appendChild(div);
            });
        }

        // Certifications
        if (prevCertsList) {
            prevCertsList.innerHTML = '';
            (currentResume.certifications || []).forEach(c => {
                const div = document.createElement('div');
                div.style.fontSize = '0.82rem';
                div.style.marginBottom = '0.25rem';
                div.innerHTML = `✓ <strong>${escapeHtml(c.name)}</strong> — ${escapeHtml(c.provider || 'Official')}`;
                prevCertsList.appendChild(div);
            });
        }
    };

    const loadResumeData = async (forceRecompile = false) => {
        hideAlert();
        try {
            const data = await fetchActiveResume(forceRecompile);
            currentResume = data;

            if (roleTitleEl) roleTitleEl.textContent = data.target_role || 'Target Role';
            if (companyTitleEl) companyTitleEl.textContent = data.target_company || 'Target Company';
            if (atsScoreEl) atsScoreEl.textContent = `${data.ats_score || 85}%`;
            if (roleAlignmentEl) roleAlignmentEl.textContent = `${data.role_alignment_score || 88}%`;
            if (completenessEl) completenessEl.textContent = `${data.completeness_score || 90}%`;

            // Populate Form
            const pInfo = data.personal_info || {};
            if (inpFullName) inpFullName.value = pInfo.full_name || '';
            if (inpEmail) inpEmail.value = pInfo.email || '';
            if (inpPhone) inpPhone.value = pInfo.phone || '';
            if (inpSummary) inpSummary.value = data.professional_summary || '';
            if (inpCoreSkills) inpCoreSkills.value = (data.technical_skills?.core || []).join(', ');

            syncPreview();
        } catch (err) {
            showAlert(err.message || "Failed to load resume.", "danger");
        }
    };

    // Event Listeners for real-time live preview syncing
    [inpFullName, inpEmail, inpPhone, inpSummary, inpCoreSkills].forEach(inp => {
        if (inp) inp.addEventListener('input', syncPreview);
    });

    if (btnRewriteSummary) {
        btnRewriteSummary.addEventListener('click', async (e) => {
            e.preventDefault();
            const original = inpSummary.value.trim();
            if (!original) return;

            btnRewriteSummary.disabled = true;
            btnRewriteSummary.textContent = "Rewriting...";

            try {
                const rewritten = await rewriteSection(
                    'summary',
                    original,
                    currentResume?.target_role || 'Software Engineer',
                    currentResume?.target_company || 'Target Company'
                );
                inpSummary.value = rewritten;
                syncPreview();
                showAlert("Professional summary rewritten for role alignment!", "success");
            } catch (err) {
                showAlert(err.message || "Rewrite failed.", "danger");
            } finally {
                btnRewriteSummary.disabled = false;
                btnRewriteSummary.textContent = "✨ AI Rewrite";
            }
        });
    }

    if (btnSave) {
        btnSave.addEventListener('click', async () => {
            if (!currentResume) return;

            currentResume.personal_info = currentResume.personal_info || {};
            currentResume.personal_info.full_name = inpFullName.value.trim();
            currentResume.personal_info.email = inpEmail.value.trim();
            currentResume.personal_info.phone = inpPhone.value.trim();
            currentResume.professional_summary = inpSummary.value.trim();

            const coreList = inpCoreSkills.value.split(',').map(s => s.trim()).filter(Boolean);
            currentResume.technical_skills = currentResume.technical_skills || {};
            currentResume.technical_skills.core = coreList;

            btnSave.disabled = true;
            btnSave.textContent = "Saving...";

            try {
                const saved = await saveResume(currentResume);
                currentResume = saved;
                if (atsScoreEl) atsScoreEl.textContent = `${saved.ats_score}%`;
                if (roleAlignmentEl) roleAlignmentEl.textContent = `${saved.role_alignment_score}%`;
                showAlert("Resume saved successfully!", "success");
            } catch (err) {
                showAlert(err.message || "Failed to save resume.", "danger");
            } finally {
                btnSave.disabled = false;
                btnSave.textContent = "Save Resume";
            }
        });
    }

    if (btnRecompile) {
        btnRecompile.addEventListener('click', () => loadResumeData(true));
    }

    if (btnPrint) {
        btnPrint.addEventListener('click', () => {
            window.print();
        });
    }

    loadResumeData();
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
