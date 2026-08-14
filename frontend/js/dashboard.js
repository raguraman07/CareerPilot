import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;


document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // 1. Sidebar Toggles (Mobile View Drawer)
    // -------------------------------------------------------------
    const hamburgerBtn = document.getElementById('hamburger-menu-btn');
    const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
    const sidebarWrapper = document.getElementById('sidebar-wrapper');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    const toggleSidebar = (forceState) => {
        const isCurrentlyActive = sidebarWrapper.classList.contains('active');
        const nextState = typeof forceState === 'boolean' ? forceState : !isCurrentlyActive;
        
        sidebarWrapper.classList.toggle('active', nextState);
        sidebarOverlay.classList.toggle('active', nextState);
        hamburgerBtn.classList.toggle('active', nextState);
        hamburgerBtn.setAttribute('aria-expanded', nextState);
    };

    if (hamburgerBtn) {
        hamburgerBtn.addEventListener('click', () => toggleSidebar());
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', () => toggleSidebar(false));
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', () => toggleSidebar(false));
    }

    // -------------------------------------------------------------
    // 2. Dropdown Actions (Notifications & User Profile)
    // -------------------------------------------------------------
    const notifBtn = document.getElementById('notification-btn');
    const notifDropdown = document.getElementById('notif-dropdown');
    const profileBtn = document.getElementById('profile-dropdown-btn');
    const profileDropdown = document.getElementById('profile-dropdown');

    const closeAllDropdowns = () => {
        if (notifDropdown) {
            notifDropdown.classList.remove('show');
            notifBtn.setAttribute('aria-expanded', 'false');
        }
        if (profileDropdown) {
            profileDropdown.classList.remove('show');
            profileBtn.setAttribute('aria-expanded', 'false');
        }
    };

    const toggleDropdown = (btn, dropdown) => {
        if (!btn || !dropdown) return;
        const isShown = dropdown.classList.contains('show');
        closeAllDropdowns();
        if (!isShown) {
            dropdown.classList.add('show');
            btn.setAttribute('aria-expanded', 'true');
        }
    };

    if (notifBtn && notifDropdown) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(notifBtn, notifDropdown);
        });
    }

    if (profileBtn && profileDropdown) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(profileBtn, profileDropdown);
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        const clickedInsideNotif = notifDropdown?.contains(e.target) || notifBtn?.contains(e.target);
        const clickedInsideProfile = profileDropdown?.contains(e.target) || profileBtn?.contains(e.target);
        
        if (!clickedInsideNotif && !clickedInsideProfile) {
            closeAllDropdowns();
        }
    });

    // Prevent dropdown container clicks from closing
    if (notifDropdown) notifDropdown.addEventListener('click', (e) => e.stopPropagation());
    if (profileDropdown) profileDropdown.addEventListener('click', (e) => e.stopPropagation());


    // -------------------------------------------------------------
    // 3. Statistics Cards Rendering
    // -------------------------------------------------------------
    const statsContainer = document.getElementById('dashboard-stats-grid');
    const statsData = [
        {
            label: "ATS Score",
            value: "84%",
            statusText: "+4% since last scan",
            trend: "up",
            icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
            isSeal: true
        },
        {
            label: "Resume Status",
            value: "Active",
            statusText: "Uploaded 2 days ago",
            trend: "none",
            icon: `<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`,
            isSeal: false
        },
        {
            label: "Job Match Score",
            value: "72%",
            statusText: "Target: Software Engineer",
            trend: "up",
            icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><path d="M8.56 2.75c4.37 6.03 6.02 9.42 8.03 17.72"></path><path d="M2 12h20"></path></svg>`,
            isSeal: false
        },
        {
            label: "Interview Questions",
            value: "15",
            statusText: "12 generated this week",
            trend: "up",
            icon: `<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`,
            isSeal: false
        }
    ];

    const renderStats = () => {
        if (!statsContainer) return;
        statsContainer.innerHTML = statsData.map(stat => {
            const trendClass = stat.trend === 'up' ? 'up' : (stat.trend === 'down' ? 'down' : '');
            const trendArrow = stat.trend === 'up' ? '↑' : (stat.trend === 'down' ? '↓' : '');
            
            return `
                <article class="metric-card ${stat.isSeal ? 'ats-score-card' : ''}">
                    <div class="metric-content">
                        <span class="metric-label">${stat.label}</span>
                        <span class="metric-val mono-figure">${stat.value}</span>
                        <div class="metric-status-row">
                            ${stat.trend !== 'none' ? `<span class="metric-trend ${trendClass}">${trendArrow}</span>` : ''}
                            <span class="metric-subtext">${stat.statusText}</span>
                        </div>
                    </div>
                    <div class="metric-icon-badge" aria-hidden="true">
                        ${stat.icon}
                    </div>
                </article>
            `;
        }).join('');
    };

    renderStats();


    // -------------------------------------------------------------
    // 4. Recent Activity Log Rendering
    // -------------------------------------------------------------
    const activityTbody = document.getElementById('activity-tbody');
    const refreshBtn = document.getElementById('btn-refresh-activity');
    
    let activitiesData = [
        {
            date: "2026-07-11",
            activity: "Resume parsed & ATS score computed",
            status: "completed",
            statusCode: "success"
        },
        {
            date: "2026-07-10",
            activity: "Job Match check against 'Backend Engineer (Flask/Python)'",
            status: "analyzed",
            statusCode: "info"
        },
        {
            date: "2026-07-09",
            activity: "Interview prep session: behavioral questions",
            status: "generated",
            statusCode: "warning"
        },
        {
            date: "2026-07-08",
            activity: "Registered account and setup user profile",
            status: "completed",
            statusCode: "success"
        }
    ];

    const renderActivities = () => {
        if (!activityTbody) return;
        if (activitiesData.length === 0) {
            activityTbody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        No recent activities recorded.
                    </td>
                </tr>
            `;
            return;
        }

        activityTbody.innerHTML = activitiesData.map(row => `
            <tr>
                <td class="date-col">${row.date}</td>
                <td class="activity-col">${row.activity}</td>
                <td>
                    <span class="status-badge ${row.statusCode}">${row.status}</span>
                </td>
            </tr>
        `).join('');
    };

    renderActivities();

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            // Visual loading feedback
            const refreshSvg = refreshBtn.querySelector('svg');
            if (refreshSvg) {
                refreshSvg.style.transition = 'transform 0.8s ease';
                refreshSvg.style.transform = 'rotate(360deg)';
                setTimeout(() => {
                    refreshSvg.style.transition = 'none';
                    refreshSvg.style.transform = 'rotate(0)';
                }, 800);
            }

            // Simulate fetching new logs
            setTimeout(() => {
                const dates = ["2026-07-11", "2026-07-10", "2026-07-09", "2026-07-08"];
                const mockLogs = [
                    { date: dates[0], activity: "AI Career Coach consultation regarding Resume Gaps", status: "completed", statusCode: "success" },
                    { date: dates[0], activity: "Exported Roadmap report to PDF", status: "completed", statusCode: "success" },
                    { date: dates[1], activity: "Re-analyzed resume file: Resume_v2_final.pdf", status: "completed", statusCode: "success" },
                ];
                
                // Add one random mock item at the beginning
                const randomLog = mockLogs[Math.floor(Math.random() * mockLogs.length)];
                
                // Ensure we don't spam duplicate random items in front
                if (activitiesData[0]?.activity !== randomLog.activity) {
                    activitiesData.unshift(randomLog);
                    if (activitiesData.length > 6) activitiesData.pop(); // Cap length
                }
                
                renderActivities();
            }, 300);
        });
    }


    // -------------------------------------------------------------
    // 5. Notifications List Dropdown Handling
    // -------------------------------------------------------------
    const notifListContainer = document.getElementById('notif-list');
    const notifBadge = document.getElementById('notif-badge');
    const markReadBtn = document.getElementById('mark-all-read');

    let notificationsData = [
        { id: 1, text: "Resume analysis completed. ATS Score is 84/100.", time: "10m ago", unread: true },
        { id: 2, text: "New mock interview questions are ready for practice.", time: "1h ago", unread: true },
        { id: 3, text: "System databases migrated to staging environment.", time: "1d ago", unread: false }
    ];

    const updateNotifBadge = () => {
        if (!notifBadge) return;
        const unreadCount = notificationsData.filter(n => n.unread).length;
        if (unreadCount > 0) {
            notifBadge.textContent = unreadCount;
            notifBadge.style.display = 'flex';
        } else {
            notifBadge.style.display = 'none';
        }
    };

    const renderNotifications = () => {
        if (!notifListContainer) return;
        if (notificationsData.length === 0) {
            notifListContainer.innerHTML = `
                <li style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.82rem;">
                    All caught up! No notifications.
                </li>
            `;
            return;
        }

        notifListContainer.innerHTML = notificationsData.map(notif => `
            <li class="notif-item ${notif.unread ? 'unread' : ''}" data-id="${notif.id}" role="menuitem" tabindex="0">
                ${notif.unread ? `<div class="notif-dot" aria-hidden="true"></div>` : `<div style="width: 8px;"></div>`}
                <div class="notif-content">
                    <p class="notif-msg">${notif.text}</p>
                    <span class="notif-time">${notif.time}</span>
                </div>
            </li>
        `).join('');

        // Attach click listeners to individual notifications to mark as read
        notifListContainer.querySelectorAll('.notif-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = parseInt(item.getAttribute('data-id'), 10);
                const notif = notificationsData.find(n => n.id === id);
                if (notif && notif.unread) {
                    notif.unread = false;
                    updateNotifBadge();
                    renderNotifications();
                }
            });
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    item.click();
                }
            });
        });
    };

    if (markReadBtn) {
        markReadBtn.addEventListener('click', () => {
            notificationsData.forEach(n => n.unread = false);
            updateNotifBadge();
            renderNotifications();
        });
    }

    // Initial render
    updateNotifBadge();
    renderNotifications();


    // -------------------------------------------------------------
    // 6. Search Bar Shortcut and Actions Filtering
    // -------------------------------------------------------------
    const searchInput = document.getElementById('navbar-search');
    const actionCards = document.querySelectorAll('.action-card');

    // Key bind / to focus search
    document.addEventListener('keydown', (e) => {
        // Only trigger focus if user is not currently writing in another input or textarea
        const activeTagName = document.activeElement.tagName.toLowerCase();
        if (activeTagName !== 'input' && activeTagName !== 'textarea') {
            if (e.key === '/') {
                e.preventDefault();
                searchInput?.focus();
            }
        }
    });

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            
            actionCards.forEach(card => {
                const title = card.querySelector('h3')?.textContent.toLowerCase() || '';
                const desc = card.querySelector('p')?.textContent.toLowerCase() || '';
                
                if (title.includes(query) || desc.includes(query)) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }

    // -------------------------------------------------------------
    // 7. Dynamic AI Resume Analysis Integration
    // -------------------------------------------------------------
    const loadLatestAIAnalysis = async () => {
        const insightsPanel = document.getElementById('dashboard-ai-insights-panel');
        const statusEl = document.getElementById('dashboard-analysis-status');
        const dateEl = document.getElementById('dashboard-analysis-date');
        const formatSummaryEl = document.getElementById('dashboard-format-summary');
        const insightsList = document.getElementById('dashboard-insights-list');

        if (!insightsPanel) return;

        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;

            const res = await fetch(`${API_BASE_URL}/api/analysis/latest`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!res.ok) {
                insightsPanel.style.display = 'none';
                return;
            }

            const data = await res.json();
            if (data && data.analysis_results) {
                const results = data.analysis_results;
                insightsPanel.style.display = 'block';

                statusEl.textContent = data.status || 'Analyzed';
                
                // Format the created_at timestamp
                const dateObj = data.created_at ? new Date(data.created_at) : new Date();
                dateEl.textContent = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                formatSummaryEl.textContent = results.resume_formatting?.readability || 'N/A';

                // Render top 3 recommendations
                insightsList.innerHTML = '';
                const recs = results.actionable_recommendations || [];
                recs.slice(0, 3).forEach(rec => {
                    const li = document.createElement('li');
                    li.className = 'analysis-list-item strength-item';
                    li.textContent = rec;
                    insightsList.appendChild(li);
                });

                // Dynamically update Resume Status KPI card
                const statusCard = statsData.find(s => s.label === "Resume Status");
                if (statusCard) {
                    statusCard.value = "Analyzed";
                    statusCard.statusText = "AI review completed";
                    renderStats();
                }
            }
        } catch (err) {
            console.error("Failed to load latest AI analysis for dashboard:", err);
            insightsPanel.style.display = 'none';
        }
    };

    // Hook auth state to fetch latest analysis once available
    supabase.auth.onAuthStateChange((event, session) => {
        if (session) {
            loadLatestAIAnalysis();
        }
    });
});