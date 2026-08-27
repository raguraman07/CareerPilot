// CareerPilot AI — Integrated Resume Builder & Studio Controller
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';
import { compileTemplate } from './templates.js';
import { API_BASE_URL } from './config.js';

/**
 * Retrieve active Firebase auth token
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
 * Fetch or compile targeted resume from backend
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
 * Save resume changes to Firestore/Backend
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
 * AI suggest / rewrite
 */
export async function fetchAiSuggestions(type, text, targetRole, targetCompany) {
    const token = await getAuthToken();
    try {
        const response = await fetch(`${API_BASE_URL}/api/ai-suggest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify({
                type: type,
                text: text,
                target_role: targetRole,
                target_company: targetCompany
            })
        });
        if (response.ok) {
            return await response.json();
        }
    } catch (err) {
        console.error("AI suggest call failed:", err);
    }
    return null;
}

// -------------------------------------------------------------
// Core UI State & Controller Handlers
// -------------------------------------------------------------
let currentResumeState = null;
let zoomLevel = 1.0;
let autoSaveTimer = null;
let activeModalTarget = null;

document.addEventListener('DOMContentLoaded', async () => {
    const pageShell = document.getElementById('resume-builder-page-shell');
    if (!pageShell) return;

    // Stepper & Panes
    const stepPanes = [
        'step-pane-personal',
        'step-pane-summary',
        'step-pane-experience',
        'step-pane-education',
        'step-pane-skills',
        'step-pane-projects',
        'step-pane-certifications'
    ];
    let currentStepIdx = 0;

    const stepperBubbles = document.querySelectorAll('.step-bubble');
    const btnWizardPrev = document.getElementById('btn-wizard-prev');
    const btnWizardNext = document.getElementById('btn-wizard-next');

    // Header & Alert
    const roleTitleEl = document.getElementById('builder-role-title');
    const companyTitleEl = document.getElementById('builder-company-title');
    const atsScoreEl = document.getElementById('builder-ats-score');
    const roleAlignmentEl = document.getElementById('builder-role-alignment');
    const completenessEl = document.getElementById('builder-completeness');
    const alertBox = document.getElementById('builder-alert-box');
    const saveStatusBadge = document.getElementById('save-status-badge');

    // Controls
    const btnSaveMain = document.getElementById('btn-save-resume-main');
    const btnRecompile = document.getElementById('btn-recompile-targeted');
    const btnExportPdf = document.getElementById('btn-export-pdf');
    const templateSelector = document.getElementById('template-selector');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnFullscreen = document.getElementById('btn-fullscreen-toggle');
    const previewWrapper = document.getElementById('preview-container-wrapper');
    const previewPaper = document.getElementById('resume-preview-paper');

    // Drawers & Modals
    const btnToggleStyles = document.getElementById('btn-toggle-styles-drawer');
    const stylesDrawer = document.getElementById('styles-slide-drawer');
    const btnCloseStyles = document.getElementById('btn-close-styles-drawer');

    const aiModal = document.getElementById('ai-suggestion-modal');
    const aiOutput = document.getElementById('ai-suggestion-output');
    const btnCloseAi = document.getElementById('btn-close-ai-modal');
    const btnCancelAi = document.getElementById('btn-cancel-ai-modal');
    const btnApplyAi = document.getElementById('btn-apply-ai-modal');
    const btnEnhanceSummary = document.getElementById('btn-enhance-summary');

    // Form Inputs
    const inpFullName = document.getElementById('inp-fullname');
    const inpJobTitle = document.getElementById('inp-jobtitle');
    const inpEmail = document.getElementById('inp-email');
    const inpPhone = document.getElementById('inp-phone');
    const inpAddress = document.getElementById('inp-address');
    const inpLinkedIn = document.getElementById('inp-linkedin');
    const inpGithub = document.getElementById('inp-github');
    const inpPortfolio = document.getElementById('inp-portfolio');
    const inpSummary = document.getElementById('inp-summary');
    const inpPhotoFile = document.getElementById('inp-photo-file');
    const photoPreviewEl = document.getElementById('resume-photo-preview');
    const btnRemovePhoto = document.getElementById('btn-remove-photo');

    // Style Selectors
    const styleFontSelect = document.getElementById('style-font-select');
    const styleLayoutSelect = document.getElementById('style-layout-select');
    const styleSpacingSelect = document.getElementById('style-spacing-select');
    const colorSwatches = document.querySelectorAll('.swatch-circle');

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
    };

    // ---------------------------------------------------------
    // 1. Live Reactive Canvas Preview Sync
    // ---------------------------------------------------------
    const readFormValues = () => {
        if (!currentResumeState) return;

        currentResumeState.resumeData = currentResumeState.resumeData || {};
        currentResumeState.customStyle = currentResumeState.customStyle || {};
        const data = currentResumeState.resumeData;

        // Personal Info
        const photoImg = photoPreviewEl ? photoPreviewEl.querySelector('img') : null;
        data.personalInfo = {
            fullName: inpFullName?.value || '',
            jobTitle: inpJobTitle?.value || '',
            email: inpEmail?.value || '',
            phone: inpPhone?.value || '',
            address: inpAddress?.value || '',
            linkedIn: inpLinkedIn?.value || '',
            github: inpGithub?.value || '',
            portfolio: inpPortfolio?.value || '',
            summary: inpSummary?.value || '',
            photo: photoImg ? photoImg.src : ''
        };

        // Work Experience
        data.experience = [];
        document.querySelectorAll('.experience-entry-card').forEach(card => {
            data.experience.push({
                role: card.querySelector('.exp-role')?.value || '',
                company: card.querySelector('.exp-company')?.value || '',
                startDate: card.querySelector('.exp-start')?.value || '',
                endDate: card.querySelector('.exp-end')?.value || '',
                description: card.querySelector('.exp-desc')?.value || ''
            });
        });

        // Education
        data.education = [];
        document.querySelectorAll('.education-entry-card').forEach(card => {
            data.education.push({
                degree: card.querySelector('.edu-degree')?.value || '',
                institution: card.querySelector('.edu-inst')?.value || '',
                startDate: card.querySelector('.edu-start')?.value || '',
                endDate: card.querySelector('.edu-end')?.value || '',
                grade: card.querySelector('.edu-grade')?.value || ''
            });
        });

        // Skills (Categories + Tags)
        data.skills = [];
        document.querySelectorAll('.skill-entry-card').forEach(card => {
            const catName = card.querySelector('.skill-cat-input')?.value || 'Technical Skills';
            const tags = [];
            card.querySelectorAll('.skill-pill-tag span').forEach(tag => tags.push(tag.textContent));
            data.skills.push({ name: catName, tags: tags });
        });

        // Projects
        data.projects = [];
        document.querySelectorAll('.project-entry-card').forEach(card => {
            data.projects.push({
                name: card.querySelector('.proj-name')?.value || '',
                technologiesUsed: card.querySelector('.proj-tech')?.value || '',
                liveUrl: card.querySelector('.proj-url')?.value || '',
                description: card.querySelector('.proj-desc')?.value || ''
            });
        });

        // Certifications
        data.certifications = [];
        document.querySelectorAll('.cert-input-entry').forEach(inp => {
            if (inp.value.trim()) data.certifications.push(inp.value.trim());
        });

        // Custom Sections
        data.customSections = [];
        document.querySelectorAll('.custom-section-entry').forEach(card => {
            data.customSections.push({
                sectionTitle: card.querySelector('.custom-sect-title')?.value || '',
                sectionContent: card.querySelector('.custom-sect-content')?.value || ''
            });
        });

        // Style
        currentResumeState.templateId = templateSelector?.value || currentResumeState.templateId || 'modern_professional';
        currentResumeState.customStyle.fontFamily = styleFontSelect?.value || 'Inter';
        currentResumeState.customStyle.layout = styleLayoutSelect?.value || 'two';
        currentResumeState.customStyle.spacing = styleSpacingSelect?.value || 'comfortable';
    };

    const updatePreview = () => {
        if (!previewPaper || !currentResumeState) return;
        readFormValues();
        const html = compileTemplate(currentResumeState.templateId, currentResumeState.resumeData, currentResumeState.customStyle);
        previewPaper.innerHTML = html;
    };

    const saveDocumentDebounced = () => {
        if (saveStatusBadge) saveStatusBadge.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Saving...';
        if (autoSaveTimer) clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(async () => {
            readFormValues();
            try {
                const saved = await saveResume(currentResumeState);
                if (saved) {
                    currentResumeState = saved;
                    if (saveStatusBadge) saveStatusBadge.innerHTML = '<i class="fas fa-check-circle" style="color: var(--success);"></i> Saved';
                }
            } catch (err) {
                if (saveStatusBadge) saveStatusBadge.innerHTML = '<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> Save Error';
            }
        }, 2000);
    };

    // ---------------------------------------------------------
    // 2. Wizard Stepper Navigation
    // ---------------------------------------------------------
    const showStep = (idx) => {
        currentStepIdx = idx;
        stepPanes.forEach((paneId, i) => {
            const el = document.getElementById(paneId);
            if (el) el.classList.toggle('active', i === idx);
        });

        stepperBubbles.forEach((bubble, i) => {
            bubble.classList.remove('active', 'completed');
            if (i === idx) bubble.classList.add('active');
            else if (i < idx) bubble.classList.add('completed');
        });

        if (btnWizardPrev) btnWizardPrev.style.visibility = idx === 0 ? 'hidden' : 'visible';
        if (btnWizardNext) btnWizardNext.innerHTML = idx === stepPanes.length - 1 ? '<i class="fas fa-check"></i> Finish & Save' : 'Next <i class="fas fa-arrow-right"></i>';
    };

    stepperBubbles.forEach((bubble, i) => {
        bubble.addEventListener('click', () => {
            readFormValues();
            showStep(i);
            updatePreview();
        });
    });

    if (btnWizardPrev) {
        btnWizardPrev.addEventListener('click', () => {
            if (currentStepIdx > 0) {
                readFormValues();
                showStep(currentStepIdx - 1);
                updatePreview();
            }
        });
    }

    if (btnWizardNext) {
        btnWizardNext.addEventListener('click', async () => {
            if (currentStepIdx < stepPanes.length - 1) {
                readFormValues();
                showStep(currentStepIdx + 1);
                updatePreview();
            } else {
                readFormValues();
                try {
                    btnWizardNext.disabled = true;
                    btnWizardNext.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
                    await saveResume(currentResumeState);
                    showAlert("Resume successfully saved!", "success");
                } catch (e) {
                    showAlert(e.message || "Failed to save resume.", "danger");
                } finally {
                    btnWizardNext.disabled = false;
                    btnWizardNext.innerHTML = '<i class="fas fa-check"></i> Finish & Save';
                }
            }
        });
    }

    // ---------------------------------------------------------
    // 3. Dynamic Lists Factory Helpers
    // ---------------------------------------------------------
    const addExperienceItem = (val = {}) => {
        const container = document.getElementById('experience-list-container');
        if (!container) return;

        const card = document.createElement('div');
        card.className = 'dynamic-entry-card experience-entry-card';
        card.innerHTML = `
            <div class="dynamic-entry-header">
                <h4>Work Experience Block</h4>
                <button type="button" class="btn-remove-entry"><i class="fas fa-trash-alt"></i> Remove</button>
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Job Title / Role</label>
                <input type="text" class="builder-input exp-role" value="${escapeHtml(val.role || '')}" placeholder="e.g. Software Engineer Intern">
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Company / Employer</label>
                <input type="text" class="builder-input exp-company" value="${escapeHtml(val.company || '')}" placeholder="e.g. Google / Microsoft">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="builder-form-group">
                    <label class="builder-form-label">Start Date</label>
                    <input type="text" class="builder-input exp-start" value="${escapeHtml(val.startDate || '')}" placeholder="e.g. Jun 2023">
                </div>
                <div class="builder-form-group">
                    <label class="builder-form-label">End Date</label>
                    <input type="text" class="builder-input exp-end" value="${escapeHtml(val.endDate || '')}" placeholder="e.g. Present">
                </div>
            </div>
            <div class="builder-form-group">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <label class="builder-form-label" style="margin-bottom: 0;">Impact & Responsibilities</label>
                    <button type="button" class="btn btn-secondary btn-sm btn-ai-bullet-assist" style="padding: 2px 8px; font-size: 0.72rem;">
                        <i class="fas fa-magic" style="color: var(--primary);"></i> AI Enhance
                    </button>
                </div>
                <textarea class="builder-textarea exp-desc" rows="4" placeholder="Describe achievements (Action + Impact + Outcome)...">${escapeHtml(val.description || '')}</textarea>
            </div>
        `;

        card.querySelector('.btn-remove-entry').addEventListener('click', () => {
            card.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        card.querySelectorAll('input, textarea').forEach(inp => {
            inp.addEventListener('input', () => {
                updatePreview();
                saveDocumentDebounced();
            });
        });

        card.querySelector('.btn-ai-bullet-assist')?.addEventListener('click', () => {
            const ta = card.querySelector('.exp-desc');
            openAiModal(ta, 'experience');
        });

        container.appendChild(card);
    };

    const addEducationItem = (val = {}) => {
        const container = document.getElementById('education-list-container');
        if (!container) return;

        const card = document.createElement('div');
        card.className = 'dynamic-entry-card education-entry-card';
        card.innerHTML = `
            <div class="dynamic-entry-header">
                <h4>Academic Record</h4>
                <button type="button" class="btn-remove-entry"><i class="fas fa-trash-alt"></i> Remove</button>
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Degree / Qualification</label>
                <input type="text" class="builder-input edu-degree" value="${escapeHtml(val.degree || '')}" placeholder="e.g. B.Tech in Computer Science">
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Institution / College</label>
                <input type="text" class="builder-input edu-inst" value="${escapeHtml(val.institution || '')}" placeholder="e.g. University Name">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="builder-form-group">
                    <label class="builder-form-label">Start</label>
                    <input type="text" class="builder-input edu-start" value="${escapeHtml(val.startDate || '')}" placeholder="e.g. 2022">
                </div>
                <div class="builder-form-group">
                    <label class="builder-form-label">End / Graduation</label>
                    <input type="text" class="builder-input edu-end" value="${escapeHtml(val.endDate || '')}" placeholder="e.g. 2026">
                </div>
                <div class="builder-form-group">
                    <label class="builder-form-label">CGPA / Grade</label>
                    <input type="text" class="builder-input edu-grade" value="${escapeHtml(val.grade || '')}" placeholder="e.g. 8.8 / 10.0">
                </div>
            </div>
        `;

        card.querySelector('.btn-remove-entry').addEventListener('click', () => {
            card.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        card.querySelectorAll('input').forEach(inp => {
            inp.addEventListener('input', () => {
                updatePreview();
                saveDocumentDebounced();
            });
        });

        container.appendChild(card);
    };

    const addSkillCategoryItem = (val = {}) => {
        const container = document.getElementById('skills-list-container');
        if (!container) return;

        const card = document.createElement('div');
        card.className = 'dynamic-entry-card skill-entry-card';
        card.innerHTML = `
            <div class="dynamic-entry-header">
                <h4>Skill Category Group</h4>
                <button type="button" class="btn-remove-entry"><i class="fas fa-trash-alt"></i> Remove</button>
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Category Title</label>
                <input type="text" class="builder-input skill-cat-input" value="${escapeHtml(val.name || 'Technical Skills')}" placeholder="e.g. Core Languages / Frameworks / Cloud">
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Skills (Press Enter or comma to add)</label>
                <div class="tags-wrapper-box">
                    <input type="text" class="tag-raw-input" placeholder="e.g. Python, Docker...">
                </div>
            </div>
        `;

        const tagsWrapper = card.querySelector('.tags-wrapper-box');
        const tagInput = card.querySelector('.tag-raw-input');

        const appendTag = (text) => {
            if (!text || !text.trim()) return;
            const tagEl = document.createElement('span');
            tagEl.className = 'skill-pill-tag';
            tagEl.innerHTML = `<span>${escapeHtml(text.trim())}</span><button type="button">&times;</button>`;
            tagEl.querySelector('button').addEventListener('click', () => {
                tagEl.remove();
                updatePreview();
                saveDocumentDebounced();
            });
            tagsWrapper.insertBefore(tagEl, tagInput);
            updatePreview();
            saveDocumentDebounced();
        };

        tagInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                appendTag(tagInput.value);
                tagInput.value = '';
            }
        });
        tagInput.addEventListener('blur', () => {
            if (tagInput.value.trim()) {
                appendTag(tagInput.value);
                tagInput.value = '';
            }
        });

        if (Array.isArray(val.tags)) {
            val.tags.forEach(t => appendTag(t));
        }

        card.querySelector('.btn-remove-entry').addEventListener('click', () => {
            card.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        card.querySelector('.skill-cat-input').addEventListener('input', () => {
            updatePreview();
            saveDocumentDebounced();
        });

        container.appendChild(card);
    };

    const addProjectItem = (val = {}) => {
        const container = document.getElementById('projects-list-container');
        if (!container) return;

        const card = document.createElement('div');
        card.className = 'dynamic-entry-card project-entry-card';
        card.innerHTML = `
            <div class="dynamic-entry-header">
                <h4>Project Profile</h4>
                <button type="button" class="btn-remove-entry"><i class="fas fa-trash-alt"></i> Remove</button>
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Project Title</label>
                <input type="text" class="builder-input proj-name" value="${escapeHtml(val.name || '')}" placeholder="e.g. Cloud Deployment Monitoring System">
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <div class="builder-form-group">
                    <label class="builder-form-label">Technologies Used</label>
                    <input type="text" class="builder-input proj-tech" value="${escapeHtml(val.technologiesUsed || '')}" placeholder="e.g. Python, Docker, FastAPI">
                </div>
                <div class="builder-form-group">
                    <label class="builder-form-label">Project URL / GitHub</label>
                    <input type="text" class="builder-input proj-url" value="${escapeHtml(val.liveUrl || '')}" placeholder="e.g. https://github.com/user/project">
                </div>
            </div>
            <div class="builder-form-group">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <label class="builder-form-label" style="margin-bottom: 0;">Description & Key Outcomes</label>
                    <button type="button" class="btn btn-secondary btn-sm btn-ai-proj-assist" style="padding: 2px 8px; font-size: 0.72rem;">
                        <i class="fas fa-magic" style="color: var(--primary);"></i> AI Enhance
                    </button>
                </div>
                <textarea class="builder-textarea proj-desc" rows="3" placeholder="Engineered and deployed...">${escapeHtml(val.description || '')}</textarea>
            </div>
        `;

        card.querySelector('.btn-remove-entry').addEventListener('click', () => {
            card.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        card.querySelectorAll('input, textarea').forEach(inp => {
            inp.addEventListener('input', () => {
                updatePreview();
                saveDocumentDebounced();
            });
        });

        card.querySelector('.btn-ai-proj-assist')?.addEventListener('click', () => {
            const ta = card.querySelector('.proj-desc');
            openAiModal(ta, 'experience');
        });

        container.appendChild(card);
    };

    const addCertItem = (text = '') => {
        const container = document.getElementById('certs-list-container');
        if (!container) return;

        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.gap = '8px';
        div.style.marginBottom = '8px';
        div.innerHTML = `
            <input type="text" class="builder-input cert-input-entry" value="${escapeHtml(text)}" placeholder="e.g. AWS Certified Cloud Practitioner" style="flex: 1;">
            <button type="button" class="btn-remove-entry" style="padding: 0.5rem 0.75rem;"><i class="fas fa-trash-alt"></i></button>
        `;

        div.querySelector('.btn-remove-entry').addEventListener('click', () => {
            div.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        div.querySelector('input').addEventListener('input', () => {
            updatePreview();
            saveDocumentDebounced();
        });

        container.appendChild(div);
    };

    const addCustomSectionItem = (val = {}) => {
        const container = document.getElementById('custom-sections-container');
        if (!container) return;

        const card = document.createElement('div');
        card.className = 'dynamic-entry-card custom-section-entry';
        card.innerHTML = `
            <div class="dynamic-entry-header">
                <h4>Custom Block</h4>
                <button type="button" class="btn-remove-entry"><i class="fas fa-trash-alt"></i> Remove</button>
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Section Heading</label>
                <input type="text" class="builder-input custom-sect-title" value="${escapeHtml(val.sectionTitle || '')}" placeholder="e.g. Publications / Leadership / Hackathons">
            </div>
            <div class="builder-form-group">
                <label class="builder-form-label">Content</label>
                <textarea class="builder-textarea custom-sect-content" rows="3" placeholder="Enter details...">${escapeHtml(val.sectionContent || '')}</textarea>
            </div>
        `;

        card.querySelector('.btn-remove-entry').addEventListener('click', () => {
            card.remove();
            updatePreview();
            saveDocumentDebounced();
        });

        card.querySelectorAll('input, textarea').forEach(inp => {
            inp.addEventListener('input', () => {
                updatePreview();
                saveDocumentDebounced();
            });
        });

        container.appendChild(card);
    };

    // ---------------------------------------------------------
    // 4. Data Population & Adapters from CareerPilot Context
    // ---------------------------------------------------------
    const populateFormData = (resumeDoc) => {
        if (!resumeDoc) return;
        currentResumeState = resumeDoc;

        const data = resumeDoc.resumeData || {};
        const personal = data.personalInfo || resumeDoc.personal_info || {};
        const styles = resumeDoc.customStyle || {};

        if (roleTitleEl) roleTitleEl.textContent = resumeDoc.target_role || 'Software Engineer';
        if (companyTitleEl) companyTitleEl.textContent = resumeDoc.target_company || 'Target Company';
        if (atsScoreEl) atsScoreEl.textContent = `${resumeDoc.ats_score || 88}%`;
        if (roleAlignmentEl) roleAlignmentEl.textContent = `${resumeDoc.role_alignment_score || 90}%`;
        if (completenessEl) completenessEl.textContent = `${resumeDoc.completeness_score || 95}%`;

        // Personal Info Inputs
        if (inpFullName) inpFullName.value = personal.fullName || personal.full_name || '';
        if (inpJobTitle) inpJobTitle.value = personal.jobTitle || resumeDoc.target_role || '';
        if (inpEmail) inpEmail.value = personal.email || '';
        if (inpPhone) inpPhone.value = personal.phone || '';
        if (inpAddress) inpAddress.value = personal.address || personal.location || '';
        if (inpLinkedIn) inpLinkedIn.value = personal.linkedIn || personal.linkedin_url || '';
        if (inpGithub) inpGithub.value = personal.github || personal.github_url || '';
        if (inpPortfolio) inpPortfolio.value = personal.portfolio || personal.portfolio_url || '';
        if (inpSummary) inpSummary.value = personal.summary || resumeDoc.professional_summary || '';

        // Photo Preview
        if (personal.photo && photoPreviewEl) {
            photoPreviewEl.innerHTML = `<img src="${personal.photo}" style="width: 100%; height: 100%; object-fit: cover;">`;
            if (btnRemovePhoto) btnRemovePhoto.style.display = 'inline-block';
        }

        // Work History
        const expList = data.experience || (resumeDoc.experience || []).map(e => ({
            role: e.role || e.title,
            company: e.company,
            startDate: e.start_date || e.startDate,
            endDate: e.end_date || e.endDate,
            description: e.description || (e.responsibilities || []).join('\n')
        }));
        const expContainer = document.getElementById('experience-list-container');
        if (expContainer) expContainer.innerHTML = '';
        if (expList.length > 0) expList.forEach(e => addExperienceItem(e));
        else addExperienceItem();

        // Education
        const eduList = data.education || (resumeDoc.education || []).map(ed => ({
            degree: ed.degree,
            institution: ed.institution,
            startDate: ed.start_year || ed.startDate || '2022',
            endDate: ed.graduation_year || ed.endDate || '2026',
            grade: ed.cgpa || ed.grade || ''
        }));
        const eduContainer = document.getElementById('education-list-container');
        if (eduContainer) eduContainer.innerHTML = '';
        if (eduList.length > 0) eduList.forEach(ed => addEducationItem(ed));
        else addEducationItem();

        // Skills
        const skillsContainer = document.getElementById('skills-list-container');
        if (skillsContainer) skillsContainer.innerHTML = '';
        if (Array.isArray(data.skills) && data.skills.length > 0) {
            data.skills.forEach(s => addSkillCategoryItem(s));
        } else {
            const tech = resumeDoc.technical_skills || {};
            const coreTags = tech.core || ['Python', 'Linux', 'REST APIs'];
            const suppTags = tech.supporting || ['Git', 'Docker'];
            addSkillCategoryItem({ name: 'Core Technologies', tags: coreTags });
            if (suppTags.length > 0) addSkillCategoryItem({ name: 'Tools & Frameworks', tags: suppTags });
        }

        // Projects
        const projectsContainer = document.getElementById('projects-list-container');
        if (projectsContainer) projectsContainer.innerHTML = '';
        const projList = data.projects || (resumeDoc.projects || []).map(p => ({
            name: p.title || p.name,
            technologiesUsed: (p.technologies || []).join(', '),
            liveUrl: p.github_url || p.liveUrl || '',
            description: Array.isArray(p.bullets) ? p.bullets.join('\n') : p.description
        }));
        if (projList.length > 0) projList.forEach(p => addProjectItem(p));
        else addProjectItem();

        // Certifications
        const certContainer = document.getElementById('certs-list-container');
        if (certContainer) certContainer.innerHTML = '';
        const certList = data.certifications || (resumeDoc.certifications || []).map(c => typeof c === 'string' ? c : `${c.name} (${c.provider || ''})`);
        if (certList.length > 0) certList.forEach(c => addCertItem(c));
        else addCertItem();

        // Custom Sections
        const customContainer = document.getElementById('custom-sections-container');
        if (customContainer) customContainer.innerHTML = '';
        if (Array.isArray(data.customSections)) {
            data.customSections.forEach(cs => addCustomSectionItem(cs));
        }

        // Styles
        if (templateSelector) templateSelector.value = resumeDoc.templateId || 'modern_professional';
        if (styleFontSelect) styleFontSelect.value = styles.fontFamily || 'Inter';
        if (styleLayoutSelect) styleLayoutSelect.value = styles.layout || 'two';
        if (styleSpacingSelect) styleSpacingSelect.value = styles.spacing || 'comfortable';

        const activeColor = styles.primaryColor || '#EC5B38';
        colorSwatches.forEach(sw => {
            sw.classList.toggle('active', sw.dataset.color.toLowerCase() === activeColor.toLowerCase());
        });

        updatePreview();
    };

    // Load recommendations for chip helpers
    const loadCareerPilotRecommendations = async () => {
        try {
            const token = await getAuthToken();
            if (!token) return;
            const res = await fetch(`${API_BASE_URL}/api/recommendations`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) return;
            const recData = await res.json();
            const payload = recData.data || recData;

            // Skills chips
            const skillsHelper = document.getElementById('skills-rec-helper');
            const skillsChips = document.getElementById('skills-rec-chips');
            const recSkills = payload.skills || [];
            if (skillsHelper && skillsChips && recSkills.length > 0) {
                skillsChips.innerHTML = '';
                recSkills.slice(0, 8).forEach(sk => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'rec-chip-btn';
                    btn.textContent = `+ ${sk.name || sk}`;
                    btn.addEventListener('click', () => {
                        const firstSkillCard = document.querySelector('.skill-entry-card .tags-wrapper-box');
                        const rawInp = firstSkillCard?.querySelector('.tag-raw-input');
                        if (firstSkillCard && rawInp) {
                            const tagEl = document.createElement('span');
                            tagEl.className = 'skill-pill-tag';
                            tagEl.innerHTML = `<span>${escapeHtml(sk.name || sk)}</span><button type="button">&times;</button>`;
                            tagEl.querySelector('button').addEventListener('click', () => {
                                tagEl.remove();
                                updatePreview();
                                saveDocumentDebounced();
                            });
                            firstSkillCard.insertBefore(tagEl, rawInp);
                            updatePreview();
                            saveDocumentDebounced();
                        }
                    });
                    skillsChips.appendChild(btn);
                });
                skillsHelper.style.display = 'block';
            }

            // Projects chips
            const projHelper = document.getElementById('projects-rec-helper');
            const projChips = document.getElementById('projects-rec-chips');
            const recProjects = (payload.projects?.intermediate || []).concat(payload.projects?.beginner || []);
            if (projHelper && projChips && recProjects.length > 0) {
                projChips.innerHTML = '';
                recProjects.slice(0, 3).forEach(p => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'rec-chip-btn';
                    btn.textContent = `+ ${p.title}`;
                    btn.addEventListener('click', () => {
                        addProjectItem({
                            name: p.title,
                            technologiesUsed: (p.technologies || []).join(', '),
                            description: p.description || 'Developed project implementing core target requirements.'
                        });
                        updatePreview();
                        saveDocumentDebounced();
                    });
                    projChips.appendChild(btn);
                });
                projHelper.style.display = 'block';
            }
        } catch (e) {
            console.warn("Could not load recommendation chips:", e);
        }
    };

    // ---------------------------------------------------------
    // 5. AI Rewrite Modal Engine
    // ---------------------------------------------------------
    const openAiModal = async (targetTextarea, type = 'experience') => {
        if (!targetTextarea) return;
        activeModalTarget = targetTextarea;
        const currentText = targetTextarea.value.trim();
        if (!currentText) {
            showAlert("Please enter some text in the field first so the AI has context to enhance.", "danger");
            return;
        }

        if (aiModal && aiOutput) {
            aiModal.classList.add('active');
            aiOutput.textContent = 'Generating role-aligned professional suggestion with CareerPilot AI...';

            const advice = await fetchAiSuggestions(
                type,
                currentText,
                currentResumeState?.target_role || 'Software Engineer',
                currentResumeState?.target_company || 'Target Company'
            );

            if (advice && advice.suggestion) {
                aiOutput.textContent = advice.suggestion;
            } else {
                aiOutput.textContent = `Spearheaded and executed: '${currentText}', ensuring alignment with best practices and boosting output metrics.`;
            }
        }
    };

    if (btnEnhanceSummary) {
        btnEnhanceSummary.addEventListener('click', () => openAiModal(inpSummary, 'summary'));
    }

    if (btnCloseAi) btnCloseAi.addEventListener('click', () => aiModal?.classList.remove('active'));
    if (btnCancelAi) btnCancelAi.addEventListener('click', () => aiModal?.classList.remove('active'));
    if (btnApplyAi) {
        btnApplyAi.addEventListener('click', () => {
            if (activeModalTarget && aiOutput) {
                activeModalTarget.value = aiOutput.textContent.trim();
                updatePreview();
                saveDocumentDebounced();
            }
            aiModal?.classList.remove('active');
        });
    }

    // ---------------------------------------------------------
    // 6. Style Studio Drawer & Color Swatches
    // ---------------------------------------------------------
    if (btnToggleStyles) {
        btnToggleStyles.addEventListener('click', () => stylesDrawer?.classList.toggle('active'));
    }
    if (btnCloseStyles) {
        btnCloseStyles.addEventListener('click', () => stylesDrawer?.classList.remove('active'));
    }

    colorSwatches.forEach(sw => {
        sw.addEventListener('click', () => {
            colorSwatches.forEach(s => s.classList.remove('active'));
            sw.classList.add('active');
            currentResumeState.customStyle = currentResumeState.customStyle || {};
            currentResumeState.customStyle.primaryColor = sw.dataset.color;
            updatePreview();
            saveDocumentDebounced();
        });
    });

    [styleFontSelect, styleLayoutSelect, styleSpacingSelect].forEach(sel => {
        sel?.addEventListener('change', () => {
            updatePreview();
            saveDocumentDebounced();
        });
    });

    // ---------------------------------------------------------
    // 7. Toolbar Actions (Template Switching, Zoom, PDF)
    // ---------------------------------------------------------
    if (templateSelector) {
        templateSelector.addEventListener('change', (e) => {
            currentResumeState.templateId = e.target.value;
            updatePreview();
            saveDocumentDebounced();
        });
    }

    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => {
            if (zoomLevel < 1.4) {
                zoomLevel += 0.1;
                if (previewPaper) previewPaper.style.transform = `scale(${zoomLevel})`;
            }
        });
    }

    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => {
            if (zoomLevel > 0.6) {
                zoomLevel -= 0.1;
                if (previewPaper) previewPaper.style.transform = `scale(${zoomLevel})`;
            }
        });
    }

    if (btnFullscreen) {
        btnFullscreen.addEventListener('click', () => {
            previewWrapper?.classList.toggle('fullscreen-mode');
            const icon = btnFullscreen.querySelector('i');
            if (icon) icon.className = previewWrapper?.classList.contains('fullscreen-mode') ? 'fas fa-compress' : 'fas fa-expand';
        });
    }

    if (btnExportPdf) {
        btnExportPdf.addEventListener('click', async (e) => {
            e.preventDefault();
            const originalHtml = btnExportPdf.innerHTML;
            try {
                btnExportPdf.disabled = true;
                btnExportPdf.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating PDF...';
                readFormValues();

                const templateHtml = compileTemplate(currentResumeState.templateId, currentResumeState.resumeData, currentResumeState.customStyle);
                const fullName = currentResumeState.resumeData?.personalInfo?.fullName || 'Candidate';
                const filename = `${fullName.replace(/\s+/g, '_')}_Resume.pdf`;

                const token = await getAuthToken();
                const response = await fetch(`${API_BASE_URL}/api/generate-pdf`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                    },
                    body: JSON.stringify({ html: templateHtml, filename: filename })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                    showAlert("PDF generated successfully!", "success");
                } else {
                    const errJson = await response.json().catch(() => ({}));
                    showAlert(errJson.message || "PDF generation failed on server.", "danger");
                }
            } catch (err) {
                showAlert("PDF download failed. Ensure backend Flask server is running.", "danger");
            } finally {
                btnExportPdf.disabled = false;
                btnExportPdf.innerHTML = originalHtml;
            }
        });
    }

    // Photo input upload handler
    if (inpPhotoFile && photoPreviewEl) {
        inpPhotoFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.size > 2 * 1024 * 1024) {
                showAlert("Image is too large. Please select an image smaller than 2MB.", "danger");
                return;
            }
            const reader = new FileReader();
            reader.onload = (event) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    canvas.width = 180;
                    canvas.height = 180;
                    const minDim = Math.min(img.width, img.height);
                    const sx = (img.width - minDim) / 2;
                    const sy = (img.height - minDim) / 2;
                    ctx.drawImage(img, sx, sy, minDim, minDim, 0, 0, 180, 180);
                    const base64 = canvas.toDataURL('image/jpeg', 0.85);

                    photoPreviewEl.innerHTML = `<img src="${base64}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
                    if (btnRemovePhoto) btnRemovePhoto.style.display = 'inline-block';
                    updatePreview();
                    saveDocumentDebounced();
                };
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });

        btnRemovePhoto?.addEventListener('click', () => {
            photoPreviewEl.innerHTML = `<i class="fas fa-user-alt" style="font-size: 20px; color: var(--text-secondary);"></i>`;
            if (btnRemovePhoto) btnRemovePhoto.style.display = 'none';
            if (inpPhotoFile) inpPhotoFile.value = '';
            updatePreview();
            saveDocumentDebounced();
        });
    }

    // Direct Input Change Listeners for real-time live preview syncing
    [inpFullName, inpJobTitle, inpEmail, inpPhone, inpAddress, inpLinkedIn, inpGithub, inpPortfolio, inpSummary].forEach(inp => {
        inp?.addEventListener('input', () => {
            updatePreview();
            saveDocumentDebounced();
        });
    });

    // Add Entry Button Click Handlers
    document.getElementById('btn-add-experience')?.addEventListener('click', () => {
        addExperienceItem();
        updatePreview();
        saveDocumentDebounced();
    });
    document.getElementById('btn-add-education')?.addEventListener('click', () => {
        addEducationItem();
        updatePreview();
        saveDocumentDebounced();
    });
    document.getElementById('btn-add-skill-group')?.addEventListener('click', () => {
        addSkillCategoryItem();
        updatePreview();
        saveDocumentDebounced();
    });
    document.getElementById('btn-add-project')?.addEventListener('click', () => {
        addProjectItem();
        updatePreview();
        saveDocumentDebounced();
    });
    document.getElementById('btn-add-cert')?.addEventListener('click', () => {
        addCertItem();
        updatePreview();
        saveDocumentDebounced();
    });
    document.getElementById('btn-add-custom-section')?.addEventListener('click', () => {
        addCustomSectionItem();
        updatePreview();
        saveDocumentDebounced();
    });

    if (btnSaveMain) {
        btnSaveMain.addEventListener('click', async () => {
            readFormValues();
            btnSaveMain.disabled = true;
            btnSaveMain.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            try {
                const saved = await saveResume(currentResumeState);
                if (saved) {
                    currentResumeState = saved;
                    showAlert("Resume successfully saved to your CareerPilot account!", "success");
                    if (atsScoreEl) atsScoreEl.textContent = `${saved.ats_score}%`;
                    if (roleAlignmentEl) roleAlignmentEl.textContent = `${saved.role_alignment_score}%`;
                }
            } catch (err) {
                showAlert(err.message || "Failed to save resume.", "danger");
            } finally {
                btnSaveMain.disabled = false;
                btnSaveMain.innerHTML = '<i class="fas fa-save"></i> Save Resume';
            }
        });
    }

    if (btnRecompile) {
        btnRecompile.addEventListener('click', async () => {
            btnRecompile.disabled = true;
            btnRecompile.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
            try {
                const recompiled = await fetchActiveResume(true);
                populateFormData(recompiled);
                showAlert("Resume synchronized with latest CareerPilot goal and verified skills!", "success");
            } catch (err) {
                showAlert(err.message || "Failed to sync career data.", "danger");
            } finally {
                btnRecompile.disabled = false;
                btnRecompile.innerHTML = '<i class="fas fa-magic" style="color: var(--primary);"></i> AI Sync';
            }
        });
    }

    // ---------------------------------------------------------
    // 8. Initial Load
    // ---------------------------------------------------------
    const initPage = async () => {
        hideAlert();

        // 1. Verify user has set a Career Goal first
        try {
            const goal = await getCurrentCareerGoal();
            if (!goal || !goal.company_name || !goal.job_role) {
                if (roleTitleEl) roleTitleEl.textContent = 'Set Your Target Goal';
                if (companyTitleEl) companyTitleEl.textContent = '';
                if (atsScoreEl) atsScoreEl.textContent = '0%';
                if (roleAlignmentEl) roleAlignmentEl.textContent = '0%';
                if (completenessEl) completenessEl.textContent = '0%';

                const targetBannerDesc = document.querySelector('.builder-target-info p');
                if (targetBannerDesc) {
                    targetBannerDesc.innerHTML = `You haven't configured an active career goal yet. <a href="career-goal.html" style="color: var(--primary); font-weight: 700;">Set your target company & role in Step 1</a> and complete your profile to enable AI resume compiling.`;
                }

                // Populate minimal personal info from logged-in user profile without fake experience/projects
                const { data: { session } } = await supabase.auth.getSession();
                if (session && session.user) {
                    const u = session.user;
                    if (inpFullName) inpFullName.value = u.user_metadata?.full_name || '';
                    if (inpEmail) inpEmail.value = u.email || '';
                }

                currentResumeState = {
                    templateId: 'modern_professional',
                    target_role: 'Target Role',
                    target_company: 'Target Company',
                    ats_score: 0,
                    role_alignment_score: 0,
                    completeness_score: 0,
                    resumeData: {
                        personalInfo: {
                            fullName: inpFullName?.value || '',
                            email: inpEmail?.value || '',
                            jobTitle: '',
                            phone: '',
                            address: '',
                            linkedIn: '',
                            github: '',
                            portfolio: '',
                            summary: ''
                        },
                        experience: [],
                        education: [],
                        skills: [],
                        projects: [],
                        certifications: []
                    },
                    customStyle: {
                        fontFamily: 'Inter',
                        layout: 'two',
                        spacing: 'comfortable',
                        primaryColor: '#EC5B38'
                    }
                };

                const expContainer = document.getElementById('experience-list-container');
                if (expContainer) expContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No work experience added yet. Click "+ Add Experience" below to add.</div>';

                const eduContainer = document.getElementById('education-list-container');
                if (eduContainer) eduContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No education added yet. Click "+ Add Education" below to add.</div>';

                const skillsContainer = document.getElementById('skills-list-container');
                if (skillsContainer) skillsContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No skill groups added yet. Click "+ Add Skill Group" below to add.</div>';

                const projectsContainer = document.getElementById('projects-list-container');
                if (projectsContainer) projectsContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No projects added yet. Click "+ Add Project" below to add.</div>';

                const certContainer = document.getElementById('certs-list-container');
                if (certContainer) certContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No certifications added yet. Click "+ Add Certification" below to add.</div>';

                updatePreview();
                return;
            }
        } catch (goalErr) {
            console.warn("Error checking career goal for resume builder:", goalErr);
        }

        try {
            const data = await fetchActiveResume(false);
            populateFormData(data);
            loadCareerPilotRecommendations();
        } catch (err) {
            showAlert(err.message || "Failed to load resume workspace.", "danger");
        }
    };

    initPage();
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
