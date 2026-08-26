// CareerPilot AI — Candidate Profile Frontend Client Module
import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:5000'
    : `http://${window.location.hostname}:5000`;

/**
 * Retrieve the active user's auth token
 */
export async function getAuthToken() {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    } catch (err) {
        console.error("Error retrieving auth token for candidate profile:", err);
        return null;
    }
}

/**
 * Fetch the authenticated user's Candidate Profile from the backend.
 */
export async function getCandidateProfile() {
    try {
        const token = await getAuthToken();
        if (!token) return null;

        const response = await fetch(`${API_BASE_URL}/api/profile`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            console.warn(`Candidate profile fetch returned status: ${response.status}`);
            return null;
        }

        const data = await response.json();
        return data.profile || null;
    } catch (err) {
        console.error("Failed to fetch candidate profile:", err);
        return null;
    }
}

/**
 * Update the candidate profile.
 */
export async function saveCandidateProfile(profileData) {
    const token = await getAuthToken();
    if (!token) {
        throw new Error("You must be logged in to save your career profile.");
    }

    const response = await fetch(`${API_BASE_URL}/api/profile`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(profileData)
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(result.error || "Failed to update candidate profile.");
    }

    return result.profile;
}

// -------------------------------------------------------------
// Interactive UI Handlers for candidate-profile.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const profileForm = document.getElementById('candidate-profile-form');
    if (!profileForm) return;

    // Form Fields
    const fullNameInput = document.getElementById('prof-fullname');
    const emailInput = document.getElementById('prof-email');
    const phoneInput = document.getElementById('prof-phone');
    const locationInput = document.getElementById('prof-location');

    const eduHighest = document.getElementById('prof-edu-highest');
    const eduDegree = document.getElementById('prof-edu-degree');
    const eduSpecialization = document.getElementById('prof-edu-specialization');
    const eduInstitution = document.getElementById('prof-edu-institution');
    const eduGradYear = document.getElementById('prof-edu-gradyear');

    const expYears = document.getElementById('prof-exp-years');
    const expRole = document.getElementById('prof-exp-role');
    const expPrevRoles = document.getElementById('prof-exp-prevroles');
    const expPrevCompanies = document.getElementById('prof-exp-prevcompanies');
    const expResponsibilities = document.getElementById('prof-exp-responsibilities');

    // UI Interactive Containers
    const statusCards = document.querySelectorAll('.career-status-card');
    const alertBox = document.getElementById('profile-alert-box');
    const submitBtn = document.getElementById('btn-save-profile');
    const completenessBar = document.getElementById('completeness-bar-fill');
    const completenessText = document.getElementById('completeness-score-val');

    // Career Goal Linkage elements
    const goalCompanyText = document.getElementById('prof-goal-company');
    const goalRoleText = document.getElementById('prof-goal-role');
    const goalExpText = document.getElementById('prof-goal-exp');
    const goalTimelineText = document.getElementById('prof-goal-timeline');
    const goalCard = document.getElementById('prof-goal-card');
    const noGoalNotice = document.getElementById('prof-no-goal-notice');

    // Resume Status Box
    const resumeStatusText = document.getElementById('prof-resume-status');
    const resumeFilenameText = document.getElementById('prof-resume-filename');
    const resumeUploadLink = document.getElementById('prof-resume-link');

    // Tag Input State Arrays
    const skillsState = {
        programming_languages: [],
        technical_skills: [],
        tools_and_technologies: [],
        soft_skills: []
    };

    // Arrays for Projects & Certifications
    let projectsList = [];
    let certificationsList = [];
    let selectedCurrentStatus = "Student";

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

    // ---------------------------------------------------------
    // Helper to Setup Tag Inputs for Skills
    // ---------------------------------------------------------
    const setupTagInput = (inputId, tagsContainerId, category) => {
        const input = document.getElementById(inputId);
        const container = document.getElementById(tagsContainerId);
        if (!input || !container) return;

        const renderTags = () => {
            container.innerHTML = '';
            skillsState[category].forEach((skill, index) => {
                const tagEl = document.createElement('span');
                tagEl.className = 'skill-tag-pill';
                tagEl.style.cssText = 'display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.3rem 0.75rem; background: var(--surface-secondary); color: var(--text-primary); border: 1px solid var(--border-light); border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 500;';
                tagEl.innerHTML = `
                    <span>${escapeHtml(skill)}</span>
                    <button type="button" aria-label="Remove ${escapeHtml(skill)}" style="background:none; border:none; color:var(--text-secondary); cursor:pointer; font-size: 1rem; line-height: 1; padding: 0;">&times;</button>
                `;
                tagEl.querySelector('button').addEventListener('click', () => {
                    skillsState[category].splice(index, 1);
                    renderTags();
                });
                container.appendChild(tagEl);
            });
        };

        const addSkill = (val) => {
            const clean = val.trim();
            if (clean && !skillsState[category].includes(clean)) {
                skillsState[category].push(clean);
                renderTags();
            }
            input.value = '';
        };

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addSkill(input.value);
            }
        });

        const addBtn = input.parentElement.querySelector('.btn-add-tag');
        if (addBtn) {
            addBtn.addEventListener('click', (e) => {
                e.preventDefault();
                addSkill(input.value);
            });
        }

        return renderTags;
    };

    const renderProgTags = setupTagInput('input-prog-skills', 'container-prog-skills', 'programming_languages');
    const renderTechTags = setupTagInput('input-tech-skills', 'container-tech-skills', 'technical_skills');
    const renderToolsTags = setupTagInput('input-tools-skills', 'container-tools-skills', 'tools_and_technologies');
    const renderSoftTags = setupTagInput('input-soft-skills', 'container-soft-skills', 'soft_skills');

    // ---------------------------------------------------------
    // Project Management
    // ---------------------------------------------------------
    const projectsContainer = document.getElementById('projects-cards-container');
    const btnAddProject = document.getElementById('btn-add-project-modal');

    const renderProjects = () => {
        if (!projectsContainer) return;
        if (projectsList.length === 0) {
            projectsContainer.innerHTML = `<p style="color: var(--text-secondary); font-size: 0.9rem; font-style: italic;">No projects added yet. (Optional for students/freshers, but highly recommended for AI job matching).</p>`;
            return;
        }

        projectsContainer.innerHTML = '';
        projectsList.forEach((proj, idx) => {
            const pCard = document.createElement('div');
            pCard.className = 'card';
            pCard.style.cssText = 'margin-bottom: 1rem; padding: 1.25rem; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--surface);';
            pCard.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                    <div>
                        <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(proj.title || 'Untitled Project')}</h4>
                        ${proj.role ? `<p style="font-size: 0.82rem; color: var(--primary); font-weight: 600; margin-top: 0.2rem;">Role: ${escapeHtml(proj.role)}</p>` : ''}
                        <p style="font-size: 0.88rem; color: var(--text-secondary); margin-top: 0.4rem;">${escapeHtml(proj.description || '')}</p>
                        ${proj.technologies && proj.technologies.length > 0 ? `
                            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem;">
                                ${proj.technologies.map(t => `<span style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--surface-secondary); border-radius: var(--radius-sm); color: var(--text-primary); font-weight: 500;">${escapeHtml(t)}</span>`).join('')}
                            </div>
                        ` : ''}
                        <div style="display:flex; gap:1rem; margin-top:0.6rem; font-size:0.85rem;">
                            ${proj.github_url ? `<a href="${escapeHtml(proj.github_url)}" target="_blank" rel="noopener" style="color: var(--primary); text-decoration: none;">GitHub Code &rarr;</a>` : ''}
                            ${proj.live_url ? `<a href="${escapeHtml(proj.live_url)}" target="_blank" rel="noopener" style="color: var(--primary); text-decoration: none;">Live Demo &rarr;</a>` : ''}
                        </div>
                    </div>
                    <button type="button" class="btn btn-outline btn-sm delete-proj-btn" data-index="${idx}" style="color: var(--danger); border-color: rgba(236,91,56,0.3); padding: 0.25rem 0.6rem;">Delete</button>
                </div>
            `;
            pCard.querySelector('.delete-proj-btn').addEventListener('click', () => {
                projectsList.splice(idx, 1);
                renderProjects();
            });
            projectsContainer.appendChild(pCard);
        });
    };

    if (btnAddProject) {
        btnAddProject.addEventListener('click', (e) => {
            e.preventDefault();
            const pTitle = prompt("Enter Project Title (e.g. CareerPilot AI):");
            if (!pTitle || !pTitle.trim()) return;

            const pDesc = prompt("Enter Short Project Description:") || "";
            const pTech = prompt("Enter Technologies used (comma separated, e.g. Python, Flask, AWS):") || "";
            const pRole = prompt("Enter Your Role in the project (optional):") || "";
            const pGithub = prompt("Enter GitHub URL (optional):") || "";
            const pLive = prompt("Enter Live App URL (optional):") || "";

            projectsList.push({
                id: 'proj-' + Date.now(),
                title: pTitle.trim(),
                description: pDesc.trim(),
                technologies: pTech.split(',').map(t => t.trim()).filter(Boolean),
                role: pRole.trim(),
                github_url: pGithub.trim(),
                live_url: pLive.trim()
            });
            renderProjects();
        });
    }

    // ---------------------------------------------------------
    // Certification Management
    // ---------------------------------------------------------
    const certsContainer = document.getElementById('certs-cards-container');
    const btnAddCert = document.getElementById('btn-add-cert-modal');

    const renderCerts = () => {
        if (!certsContainer) return;
        if (certificationsList.length === 0) {
            certsContainer.innerHTML = `<p style="color: var(--text-secondary); font-size: 0.9rem; font-style: italic;">No certifications added yet. (Optional).</p>`;
            return;
        }

        certsContainer.innerHTML = '';
        certificationsList.forEach((cert, idx) => {
            const cCard = document.createElement('div');
            cCard.className = 'card';
            cCard.style.cssText = 'margin-bottom: 1rem; padding: 1.25rem; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--surface);';
            cCard.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                    <div>
                        <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(cert.name || 'Certification')}</h4>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.2rem;">Issuing Organization: <strong style="color: var(--text-primary);">${escapeHtml(cert.issuing_organization || 'N/A')}</strong></p>
                        ${cert.issue_date ? `<p style="font-size: 0.82rem; color: var(--text-secondary);">Issued: ${escapeHtml(cert.issue_date)}</p>` : ''}
                        ${cert.credential_url ? `<p style="margin-top:0.4rem;"><a href="${escapeHtml(cert.credential_url)}" target="_blank" rel="noopener" style="font-size:0.85rem; color: var(--primary); text-decoration: none;">View Credential &rarr;</a></p>` : ''}
                    </div>
                    <button type="button" class="btn btn-outline btn-sm delete-cert-btn" data-index="${idx}" style="color: var(--danger); border-color: rgba(236,91,56,0.3); padding: 0.25rem 0.6rem;">Delete</button>
                </div>
            `;
            cCard.querySelector('.delete-cert-btn').addEventListener('click', () => {
                certificationsList.splice(idx, 1);
                renderCerts();
            });
            certsContainer.appendChild(cCard);
        });
    };

    if (btnAddCert) {
        btnAddCert.addEventListener('click', (e) => {
            e.preventDefault();
            const cName = prompt("Enter Certification Name (e.g. AWS Certified Cloud Practitioner):");
            if (!cName || !cName.trim()) return;

            const cOrg = prompt("Enter Issuing Organization (e.g. Amazon Web Services, Microsoft):") || "";
            const cDate = prompt("Enter Issue Date (e.g. 2024-01):") || "";
            const cUrl = prompt("Enter Credential URL (optional):") || "";

            certificationsList.push({
                id: 'cert-' + Date.now(),
                name: cName.trim(),
                issuing_organization: cOrg.trim(),
                issue_date: cDate.trim(),
                credential_url: cUrl.trim()
            });
            renderCerts();
        });
    }

    // ---------------------------------------------------------
    // Career Status Card Selectors
    // ---------------------------------------------------------
    statusCards.forEach(card => {
        card.addEventListener('click', () => {
            statusCards.forEach(c => c.classList.remove('active-status-card'));
            card.classList.add('active-status-card');
            selectedCurrentStatus = card.dataset.status;
        });
    });

    const updateStatusCardUI = (statusVal) => {
        selectedCurrentStatus = statusVal || "Student";
        statusCards.forEach(c => {
            if (c.dataset.status === selectedCurrentStatus) {
                c.classList.add('active-status-card');
            } else {
                c.classList.remove('active-status-card');
            }
        });
    };

    // ---------------------------------------------------------
    // Initial Load & Populate
    // ---------------------------------------------------------
    try {
        // 1. Load active Career Goal for cross-reference display
        const currentGoal = await getCurrentCareerGoal();
        if (currentGoal) {
            if (goalCard) goalCard.style.display = 'block';
            if (noGoalNotice) noGoalNotice.style.display = 'none';
            if (goalCompanyText) goalCompanyText.textContent = currentGoal.company_name;
            if (goalRoleText) goalRoleText.textContent = currentGoal.job_role;
            if (goalExpText) goalExpText.textContent = currentGoal.experience_level;
            if (goalTimelineText) goalTimelineText.textContent = currentGoal.target_timeline || 'Flexible';
        } else {
            if (goalCard) goalCard.style.display = 'none';
            if (noGoalNotice) noGoalNotice.style.display = 'block';
        }

        // 2. Load Profile
        const profile = await getCandidateProfile();
        if (profile) {
            if (fullNameInput) fullNameInput.value = profile.full_name || '';
            if (emailInput) emailInput.value = profile.email || '';
            if (phoneInput) phoneInput.value = profile.phone || '';
            if (locationInput) locationInput.value = profile.location || '';

            const edu = profile.education || {};
            if (eduHighest) eduHighest.value = edu.highest_education || '';
            if (eduDegree) eduDegree.value = edu.degree || '';
            if (eduSpecialization) eduSpecialization.value = edu.specialization || '';
            if (eduInstitution) eduInstitution.value = edu.institution || '';
            if (eduGradYear) eduGradYear.value = edu.graduation_year || '';

            const career = profile.career_information || {};
            updateStatusCardUI(career.current_status || 'Student');
            if (expYears) expYears.value = career.years_of_experience || '';
            if (expRole) expRole.value = career.current_role || '';
            if (expPrevRoles) expPrevRoles.value = career.previous_roles || '';
            if (expPrevCompanies) expPrevCompanies.value = career.previous_companies || '';
            if (expResponsibilities) expResponsibilities.value = career.major_responsibilities || '';

            const sk = profile.skills || {};
            skillsState.programming_languages = Array.isArray(sk.programming_languages) ? sk.programming_languages : [];
            skillsState.technical_skills = Array.isArray(sk.technical_skills) ? sk.technical_skills : [];
            skillsState.tools_and_technologies = Array.isArray(sk.tools_and_technologies) ? sk.tools_and_technologies : [];
            skillsState.soft_skills = Array.isArray(sk.soft_skills) ? sk.soft_skills : [];

            if (renderProgTags) renderProgTags();
            if (renderTechTags) renderTechTags();
            if (renderToolsTags) renderToolsTags();
            if (renderSoftTags) renderSoftTags();

            projectsList = Array.isArray(profile.projects) ? profile.projects : [];
            renderProjects();

            certificationsList = Array.isArray(profile.certifications) ? profile.certifications : [];
            renderCerts();

            // Resume indicator
            if (profile.resume && profile.resume.filename) {
                if (resumeStatusText) resumeStatusText.textContent = "Uploaded ✓";
                if (resumeFilenameText) resumeFilenameText.textContent = profile.resume.filename;
            } else {
                if (resumeStatusText) resumeStatusText.textContent = "Not uploaded (Optional)";
                if (resumeFilenameText) resumeFilenameText.textContent = "Upload a PDF/DOCX to enhance ATS matches";
            }

            // Completeness update
            const cScore = profile.completeness || 0;
            if (completenessBar) completenessBar.style.width = `${cScore}%`;
            if (completenessText) completenessText.textContent = `${cScore}%`;
        }
    } catch (loadErr) {
        console.error("Error populating candidate profile:", loadErr);
    }

    // ---------------------------------------------------------
    // Submit Handler
    // ---------------------------------------------------------
    profileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('loading');
            const bText = submitBtn.querySelector('.btn-text');
            if (bText) bText.textContent = "Saving Profile...";
        }

        try {
            const payload = {
                full_name: fullNameInput ? fullNameInput.value.trim() : "",
                email: emailInput ? emailInput.value.trim() : "",
                phone: phoneInput ? phoneInput.value.trim() : "",
                location: locationInput ? locationInput.value.trim() : "",
                education: {
                    highest_education: eduHighest ? eduHighest.value : "",
                    degree: eduDegree ? eduDegree.value.trim() : "",
                    specialization: eduSpecialization ? eduSpecialization.value.trim() : "",
                    institution: eduInstitution ? eduInstitution.value.trim() : "",
                    graduation_year: eduGradYear ? eduGradYear.value.trim() : ""
                },
                career_information: {
                    current_status: selectedCurrentStatus,
                    years_of_experience: expYears ? expYears.value.trim() : "0",
                    current_role: expRole ? expRole.value.trim() : "",
                    previous_roles: expPrevRoles ? expPrevRoles.value.trim() : "",
                    previous_companies: expPrevCompanies ? expPrevCompanies.value.trim() : "",
                    major_responsibilities: expResponsibilities ? expResponsibilities.value.trim() : ""
                },
                skills: {
                    programming_languages: skillsState.programming_languages,
                    technical_skills: skillsState.technical_skills,
                    tools_and_technologies: skillsState.tools_and_technologies,
                    soft_skills: skillsState.soft_skills
                },
                projects: projectsList,
                certifications: certificationsList
            };

            const updated = await saveCandidateProfile(payload);

            showAlert("Your career profile has been saved successfully!", "success");

            if (updated && typeof updated.completeness === 'number') {
                if (completenessBar) completenessBar.style.width = `${updated.completeness}%`;
                if (completenessText) completenessText.textContent = `${updated.completeness}%`;
            }

            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (err) {
            showAlert(err.message || "Failed to save profile. Please try again.", "danger");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('loading');
                const bText = submitBtn.querySelector('.btn-text');
                if (bText) bText.textContent = "Save Career Profile";
            }
        }
    });
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
