// CareerPilot AI — Job Opportunities Frontend Client Module (Module 9)
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
        console.error("Error retrieving auth token for job opportunities:", err);
        return null;
    }
}

/**
 * Fetch filtered job opportunities from backend
 */
export async function fetchJobOpportunities(filters = {}) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in to view job opportunities.");

    const queryParams = new URLSearchParams();
    if (filters.company_filter) queryParams.append('company_filter', filters.company_filter);
    if (filters.location) queryParams.append('location', filters.location);
    if (filters.experience) queryParams.append('experience', filters.experience);
    if (filters.search) queryParams.append('search', filters.search);

    const url = `${API_BASE_URL}/api/jobs/opportunities${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to load job opportunities.");
    }
    return data;
}

/**
 * Fetch detailed view for a single job opportunity
 */
export async function fetchJobDetail(jobId) {
    const token = await getAuthToken();
    if (!token) throw new Error("You must be logged in.");

    const response = await fetch(`${API_BASE_URL}/api/jobs/opportunities/${jobId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Failed to fetch job details.");
    }
    return data.job;
}

/**
 * Fetch user job notifications
 */
export async function fetchNotifications() {
    const token = await getAuthToken();
    if (!token) return { notifications: [], unread_count: 0, total_count: 0 };

    const response = await fetch(`${API_BASE_URL}/api/jobs/notifications`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) return { notifications: [], unread_count: 0, total_count: 0 };
    return await response.json();
}

/**
 * Mark a single notification as read
 */
export async function markNotificationRead(notifId) {
    const token = await getAuthToken();
    if (!token) return;

    await fetch(`${API_BASE_URL}/api/jobs/notifications/${notifId}/read`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
}

/**
 * Mark all notifications as read
 */
export async function markAllNotificationsRead() {
    const token = await getAuthToken();
    if (!token) return;

    await fetch(`${API_BASE_URL}/api/jobs/notifications/read-all`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
}

// -------------------------------------------------------------
// Interactive UI Controller for job-opportunities.html
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const pageShell = document.getElementById('jobs-page-shell');
    if (!pageShell) return;

    // Header Elements
    const roleBadgeEl = document.getElementById('target-role-badge');
    const companyBadgeEl = document.getElementById('dream-company-badge');
    const alertBox = document.getElementById('jobs-alert-box');

    // Notification Dropdown Elements
    const notifBtn = document.getElementById('btn-notif-bell');
    const notifBadge = document.getElementById('notif-unread-badge');
    const notifDropdown = document.getElementById('notif-dropdown-menu');
    const notifListContainer = document.getElementById('notif-list-items');
    const btnMarkAllRead = document.getElementById('btn-mark-all-read');

    // Filter Controls
    const searchInput = document.getElementById('job-search-input');
    const companyFilterSelect = document.getElementById('filter-company-select');
    const locationFilterSelect = document.getElementById('filter-location-select');
    const expFilterSelect = document.getElementById('filter-experience-select');
    const btnRefreshJobs = document.getElementById('btn-refresh-jobs');

    // Sections & Containers
    const unconfiguredBanner = document.getElementById('unconfigured-provider-banner');
    const dreamSection = document.getElementById('dream-company-section');
    const dreamJobList = document.getElementById('dream-company-job-list');
    const otherSection = document.getElementById('other-companies-section');
    const otherJobList = document.getElementById('other-companies-job-list');

    // Modal Elements
    const jobModal = document.getElementById('job-detail-modal');
    const btnCloseModal = document.getElementById('btn-close-job-modal');
    const modalTitle = document.getElementById('modal-job-title');
    const modalCompany = document.getElementById('modal-job-company');
    const modalLocation = document.getElementById('modal-job-location');
    const modalType = document.getElementById('modal-job-type');
    const modalExp = document.getElementById('modal-job-exp');
    const modalPosted = document.getElementById('modal-job-posted');
    const modalDesc = document.getElementById('modal-job-desc');
    const modalRespsSection = document.getElementById('modal-resps-section');
    const modalRespsList = document.getElementById('modal-job-resps');
    const modalQualsSection = document.getElementById('modal-quals-section');
    const modalQualsList = document.getElementById('modal-job-quals');
    const modalSkillsSection = document.getElementById('modal-skills-section');
    const modalSkillsList = document.getElementById('modal-job-skills');
    const modalApplyBtn = document.getElementById('modal-apply-btn');

    let currentJobData = null;

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

    // Load Header Target Career
    const loadCareerContext = async () => {
        try {
            const goal = await getCurrentCareerGoal();
            if (goal) {
                if (roleBadgeEl) roleBadgeEl.textContent = goal.job_role || 'Target Role Not Set';
                if (companyBadgeEl) companyBadgeEl.textContent = goal.company_name || 'Dream Company Not Set';
            } else {
                if (roleBadgeEl) roleBadgeEl.textContent = 'Set in Career Goal (Step 1)';
                if (companyBadgeEl) companyBadgeEl.textContent = 'Set in Career Goal (Step 1)';
            }
        } catch (e) {
            console.warn("Could not retrieve career goal context:", e);
        }
    };

    // Render Individual Job Card
    const renderJobCard = (job, isDream = false) => {
        const card = document.createElement('div');
        card.className = `job-opportunity-card ${isDream ? 'dream-card' : ''}`;
        
        const skillsList = job.skills || [];
        const skillsHtml = skillsList.length > 0
            ? `<div class="job-card-skills">${skillsList.slice(0, 4).map(s => `<span class="job-skill-chip">${escapeHtml(s)}</span>`).join('')}</div>`
            : '';

        card.innerHTML = `
            <div class="job-card-header">
                <div>
                    <span class="job-card-company">${escapeHtml(job.company || 'Company')}</span>
                    <h3 class="job-card-title">${escapeHtml(job.title || 'Job Title')}</h3>
                </div>
                ${isDream ? '<span class="dream-badge"><i class="fas fa-star"></i> Dream Company</span>' : ''}
            </div>

            <div class="job-meta-row">
                <span><i class="fas fa-map-marker-alt"></i> ${escapeHtml(job.location || 'Location')}</span>
                <span><i class="fas fa-briefcase"></i> ${escapeHtml(job.employment_type || 'Full-time')}</span>
                <span><i class="fas fa-graduation-cap"></i> ${escapeHtml(job.experience || 'Entry Level')}</span>
                <span><i class="fas fa-clock"></i> ${escapeHtml(job.posted_date || 'Recently')}</span>
            </div>

            <p class="job-card-description">${escapeHtml((job.description || '').substring(0, 160))}${job.description && job.description.length > 160 ? '...' : ''}</p>

            ${skillsHtml}

            <div class="job-card-footer">
                <button type="button" class="btn btn-secondary btn-sm btn-view-job-detail" style="font-weight: 700;">
                    View Details & Apply
                </button>
            </div>
        `;

        card.querySelector('.btn-view-job-detail').addEventListener('click', () => {
            openJobDetailModal(job);
        });

        return card;
    };

    // Open Job Details Modal
    const openJobDetailModal = (job) => {
        if (!jobModal) return;

        if (modalTitle) modalTitle.textContent = job.title || 'Job Title';
        if (modalCompany) modalCompany.textContent = job.company || 'Company';
        if (modalLocation) modalLocation.textContent = job.location || 'Not specified';
        if (modalType) modalType.textContent = job.employment_type || 'Full-time';
        if (modalExp) modalExp.textContent = job.experience || 'Not specified';
        if (modalPosted) modalPosted.textContent = job.posted_date || 'Recently';
        if (modalDesc) modalDesc.textContent = job.description || 'No description provided by the employer.';

        // Responsibilities
        if (modalRespsSection && modalRespsList) {
            const resps = job.responsibilities || [];
            if (resps.length > 0) {
                modalRespsList.innerHTML = resps.map(r => `<li>${escapeHtml(r)}</li>`).join('');
                modalRespsSection.style.display = 'block';
            } else {
                modalRespsSection.style.display = 'none';
            }
        }

        // Qualifications
        if (modalQualsSection && modalQualsList) {
            const quals = job.qualifications || [];
            if (quals.length > 0) {
                modalQualsList.innerHTML = quals.map(q => `<li>${escapeHtml(q)}</li>`).join('');
                modalQualsSection.style.display = 'block';
            } else {
                modalQualsSection.style.display = 'none';
            }
        }

        // Skills
        if (modalSkillsSection && modalSkillsList) {
            const skills = job.skills || [];
            if (skills.length > 0) {
                modalSkillsList.innerHTML = skills.map(s => `<span class="job-skill-chip">${escapeHtml(s)}</span>`).join('');
                modalSkillsSection.style.display = 'block';
            } else {
                modalSkillsSection.style.display = 'none';
            }
        }

        // Apply Link
        if (modalApplyBtn) {
            const applyUrl = job.application_url || job.job_url;
            if (applyUrl && applyUrl.startsWith('http')) {
                modalApplyBtn.href = applyUrl;
                modalApplyBtn.target = '_blank';
                modalApplyBtn.rel = 'noopener noreferrer';
                modalApplyBtn.style.display = 'inline-flex';
            } else {
                modalApplyBtn.style.display = 'none';
            }
        }

        jobModal.classList.add('active');
    };

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            jobModal?.classList.remove('active');
        });
    }

    window.addEventListener('click', (e) => {
        if (e.target === jobModal) jobModal.classList.remove('active');
    });

    // Render Notifications Dropdown
    const loadNotificationCenter = async () => {
        try {
            const notifData = await fetchNotifications();
            const unread = notifData.unread_count || 0;
            const notifs = notifData.notifications || [];

            if (notifBadge) {
                if (unread > 0) {
                    notifBadge.style.display = 'inline-flex';
                    notifBadge.textContent = unread > 9 ? '9+' : unread;
                } else {
                    notifBadge.style.display = 'none';
                }
            }

            if (notifListContainer) {
                if (notifs.length === 0) {
                    notifListContainer.innerHTML = '<div style="padding: 1.25rem; text-align: center; color: var(--text-secondary); font-size: 0.85rem; font-style: italic;">No new job notifications yet.</div>';
                } else {
                    notifListContainer.innerHTML = '';
                    notifs.forEach(n => {
                        const item = document.createElement('div');
                        item.className = `notif-dropdown-item ${n.read ? 'read' : 'unread'}`;
                        item.innerHTML = `
                            <div style="font-weight: 700; font-size: 0.88rem; color: var(--text-primary); margin-bottom: 2px;">
                                ${escapeHtml(n.title || 'Job Opportunity')}
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 4px;">
                                ${escapeHtml(n.message || '')}
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted);">
                                <span>${escapeHtml(n.location || '')}</span>
                                <span>${n.created_at ? new Date(n.created_at).toLocaleDateString() : ''}</span>
                            </div>
                        `;
                        item.addEventListener('click', async () => {
                            if (!n.read) {
                                await markNotificationRead(n.id);
                                n.read = true;
                                item.classList.remove('unread');
                                item.classList.add('read');
                                loadNotificationCenter();
                            }
                            if (n.job_id) {
                                try {
                                    const job = await fetchJobDetail(n.job_id);
                                    if (job) openJobDetailModal(job);
                                } catch (e) {}
                            }
                        });
                        notifListContainer.appendChild(item);
                    });
                }
            }
        } catch (err) {
            console.warn("Error loading notification center:", err);
        }
    };

    if (notifBtn && notifDropdown) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifDropdown.classList.toggle('active');
        });
        document.addEventListener('click', () => {
            notifDropdown.classList.remove('active');
        });
        notifDropdown.addEventListener('click', (e) => e.stopPropagation());
    }

    if (btnMarkAllRead) {
        btnMarkAllRead.addEventListener('click', async () => {
            await markAllNotificationsRead();
            loadNotificationCenter();
        });
    }

    // Main Load Opportunities Flow
    const loadJobs = async () => {
        hideAlert();
        const filters = {
            company_filter: companyFilterSelect?.value || 'ALL',
            location: locationFilterSelect?.value || '',
            experience: expFilterSelect?.value || '',
            search: searchInput?.value?.trim() || ''
        };

        try {
            if (btnRefreshJobs) {
                btnRefreshJobs.disabled = true;
                btnRefreshJobs.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
            }

            const data = await fetchJobOpportunities(filters);
            currentJobData = data;

            // Handle unconfigured provider state
            if (!data.provider_configured && (!data.total_count || data.total_count === 0)) {
                if (unconfiguredBanner) unconfiguredBanner.style.display = 'block';
                if (dreamSection) dreamSection.style.display = 'none';
                if (otherSection) otherSection.style.display = 'none';
                return;
            }

            if (unconfiguredBanner) unconfiguredBanner.style.display = 'none';

            // Render Dream Company Section
            const dreamJobs = data.dream_company_jobs || [];
            if (dreamSection && dreamJobList) {
                dreamJobList.innerHTML = '';
                if (dreamJobs.length > 0) {
                    dreamSection.style.display = 'block';
                    dreamJobs.forEach(j => dreamJobList.appendChild(renderJobCard(j, true)));
                } else {
                    dreamSection.style.display = 'block';
                    dreamJobList.innerHTML = `
                        <div class="empty-dream-state">
                            <i class="fas fa-building" style="font-size: 2rem; color: var(--text-muted); margin-bottom: 0.5rem;"></i>
                            <div style="font-weight: 600; color: var(--text-primary);">No active openings found at your Dream Company (${escapeHtml(data.dream_company || 'Target')}) right now.</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">Explore hiring opportunities for ${escapeHtml(data.target_role || 'your target role')} at other leading companies below.</div>
                        </div>
                    `;
                }
            }

            // Render Other Companies Section
            const otherJobs = data.other_company_jobs || [];
            if (otherSection && otherJobList) {
                otherJobList.innerHTML = '';
                if (otherJobs.length > 0) {
                    otherSection.style.display = 'block';
                    otherJobs.forEach(j => otherJobList.appendChild(renderJobCard(j, false)));
                } else if (dreamJobs.length === 0) {
                    otherSection.style.display = 'block';
                    otherJobList.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-secondary); font-style: italic;">No matching job opportunities found for the selected filters.</div>';
                } else {
                    otherSection.style.display = 'none';
                }
            }

        } catch (err) {
            showAlert(err.message || "Failed to load opportunities.", "danger");
        } finally {
            if (btnRefreshJobs) {
                btnRefreshJobs.disabled = false;
                btnRefreshJobs.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh Jobs';
            }
        }
    };

    // Filter Listeners
    [companyFilterSelect, locationFilterSelect, expFilterSelect].forEach(sel => {
        sel?.addEventListener('change', () => loadJobs());
    });

    let searchTimeout = null;
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            if (searchTimeout) clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => loadJobs(), 350);
        });
    }

    if (btnRefreshJobs) {
        btnRefreshJobs.addEventListener('click', () => loadJobs());
    }

    // Initialize Page
    await loadCareerContext();
    await loadNotificationCenter();
    await loadJobs();
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
