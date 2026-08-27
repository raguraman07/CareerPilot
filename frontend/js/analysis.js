/**
 * CareerPilot AI — Resume Analysis Interactivity
 * Handles loading list of resumes, triggering AI review, progress animations,
 * updating the UI card elements, loading history, and firing success/error toast notifications.
 */
import { supabase } from './supabaseClient.js';
import { renderResumeCards, renderSelectionSkeleton, renderSelectionError } from './selection.js';
import { API_BASE_URL } from './config.js';

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunAnalysis = document.getElementById('btn-run-analysis');
    const btnRetryAnalysis = document.getElementById('btn-retry-analysis');
    const form = document.getElementById('analysis-setup-form');
    
    const loadingSection = document.getElementById('analysis-loading');
    const errorSection = document.getElementById('analysis-error');
    const progressFill = document.getElementById('progress-fill');
    const progressStatus = document.getElementById('progress-status');
    const estimatedWait = document.getElementById('estimated-wait');
    const statusMsg = document.getElementById('analysis-status-msg');
    
    const resultsSection = document.getElementById('analysis-results-wrapper') || document.getElementById('analysis-results');
    const alertBox = document.getElementById('analysis-alert-box');
    const historyList = document.getElementById('history-list');
    const toastContainer = document.getElementById('toast-container');

    let isProcessing = false;

    // Helper: Toast notification alerts system
    const showToast = (message, type = 'info') => {
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        
        let iconSvg = '';
        if (type === 'success') {
            iconSvg = `<svg class="toast-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
        } else if (type === 'error') {
            iconSvg = `<svg class="toast-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
        } else {
            iconSvg = `<svg class="toast-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12.01" y2="16"></line><line x1="12" y1="8" x2="12" y2="8"></line></svg>`;
        }
        
        toast.innerHTML = `${iconSvg}<span>${message}</span>`;
        toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    };

    const showAlert = (message, type = 'danger') => {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        alertBox.textContent = message;
    };

    const hideAlert = () => {
        if (!alertBox) return;
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    };

    // Helper: Fetch authorization bearer token for authenticated user
    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    // Load available resumes to populate interactive selection cards
    const loadResumes = async () => {
        const selectContainer = document.getElementById('resume-select-container');
        if (btnRunAnalysis) btnRunAnalysis.disabled = true;
        if (selectContainer) renderSelectionSkeleton(selectContainer, 1, "Loading options...");

        try {
            const token = await getAuthToken();
            if (!token) {
                renderResumeCards(selectContainer, resumeSelect, [], (selectedId) => {
                    if (btnRunAnalysis) btnRunAnalysis.disabled = !selectedId;
                });
                return;
            }

            const response = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error("Failed to load your resumes list.");
            }

            const data = await response.json();
            
            renderResumeCards(selectContainer, resumeSelect, data, (selectedId) => {
                if (btnRunAnalysis) btnRunAnalysis.disabled = !selectedId;
            });

            checkUrlQueryParams();

        } catch (err) {
            console.error("Resume list load error:", err);
            if (selectContainer) {
                renderSelectionError(selectContainer, "Couldn't load your resumes", loadResumes);
            }
            if (btnRunAnalysis) btnRunAnalysis.disabled = true;
        }
    };

    // Load Analysis History
    const fetchHistory = async () => {
        if (!historyList) return;

        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE_URL}/api/ai/history`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error("Failed to fetch analysis history.");
            }

            const list = await response.json();
            renderHistoryList(list);

        } catch (err) {
            console.error(err);
            if (historyList) {
                historyList.innerHTML = `<li style="padding: 1rem; text-align: center; color: var(--error-color); font-size: 0.82rem;">Failed to load history list</li>`;
            }
        }
    };

    const renderHistoryList = (list) => {
        if (!historyList) return;
        if (list.length === 0) {
            historyList.innerHTML = `
                <li style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                    No previous analysis logs.
                </li>
            `;
            return;
        }

        historyList.innerHTML = list.map(item => {
            const date = new Date(item.created_at).toLocaleDateString();
            const filename = item.resumes?.filename || 'Uploaded Resume';
            
            return `
                <li class="history-item" data-id="${item.id}">
                    <div class="history-item-name" title="${filename}">${filename}</div>
                    <div class="history-item-date">Analyzed: ${date}</div>
                </li>
            `;
        }).join('');

        historyList.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                historyList.querySelectorAll('.history-item').forEach(x => x.classList.remove('active'));
                el.classList.add('active');

                const analysisId = el.getAttribute('data-id');
                const matched = list.find(x => x.id === analysisId);
                
                if (matched && matched.analysis_results) {
                    if (matched.resume_id && resumeSelect) {
                        resumeSelect.value = matched.resume_id;
                        if (btnRunAnalysis) btnRunAnalysis.disabled = false;
                    }
                    
                    if (errorSection) errorSection.style.display = 'none';
                    if (loadingSection) loadingSection.style.display = 'none';
                    renderAnalysisResults(matched.analysis_results);
                    if (resultsSection) resultsSection.style.display = 'grid';
                    
                    showToast("Loaded analysis from history cache.", "info");
                }
            });
        });
    };

    const checkUrlQueryParams = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const resumeId = urlParams.get('resume_id');
        const autoAnalyze = urlParams.get('auto_analyze') === 'true';

        if (resumeId && resumeSelect) {
            resumeSelect.value = resumeId;
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            
            if (autoAnalyze) {
                runResumeAnalysis(resumeId);
            }
        }
    };

    // Run Analysis Flow
    const runResumeAnalysis = async (resumeId) => {
        if (isProcessing) return;
        isProcessing = true;
        hideAlert();

        if (resultsSection) resultsSection.style.display = 'none';
        if (errorSection) errorSection.style.display = 'none';
        if (loadingSection) loadingSection.style.display = 'flex';
        if (estimatedWait) estimatedWait.style.display = 'block';
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'Analyzing resume...';
        }
        
        if (btnRunAnalysis) btnRunAnalysis.disabled = true;
        if (btnRetryAnalysis) btnRetryAnalysis.disabled = true;
        if (resumeSelect) resumeSelect.disabled = true;

        let secondsLeft = 5;
        if (estimatedWait) estimatedWait.textContent = `Estimated wait time: ~${secondsLeft} seconds...`;
        const countdownTimer = setInterval(() => {
            if (secondsLeft > 1) {
                secondsLeft--;
                if (estimatedWait) estimatedWait.textContent = `Estimated wait time: ~${secondsLeft} seconds...`;
            } else {
                if (estimatedWait) estimatedWait.textContent = `Wrapping up analysis details...`;
                clearInterval(countdownTimer);
            }
        }, 1000);

        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 90) {
                progress += Math.floor(Math.random() * 15) + 5;
                if (progress > 90) progress = 90;
                if (progressFill) progressFill.style.width = `${progress}%`;
                
                if (progressStatus) {
                    if (progress < 25) {
                        progressStatus.textContent = "Analyzing your resume with AI...";
                    } else if (progress < 55) {
                        progressStatus.textContent = "Extracting skills and evaluating experience...";
                    } else if (progress < 80) {
                        progressStatus.textContent = "Formulating career recommendations...";
                    } else {
                        progressStatus.textContent = "Finalizing AI analysis report...";
                    }
                }
            }
        }, 400);

        try {
            const token = await getAuthToken();
            
            const analyzeRes = await fetch(`${API_BASE_URL}/api/ai/analyze-resume`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    resume_id: resumeId
                })
            });

            clearInterval(countdownTimer);
            clearInterval(progressInterval);

            if (!analyzeRes.ok) {
                const errData = await analyzeRes.json();
                throw new Error(errData.error || "Unable to analyze resume.");
            }

            const responseData = await analyzeRes.json();
            const results = responseData.analysis?.analysis_results || responseData.analysis_results || (responseData.analysis ? responseData.analysis : responseData);

            if (progressFill) progressFill.style.width = '100%';
            if (progressStatus) progressStatus.textContent = "Resume analysis completed successfully.";
            if (estimatedWait) estimatedWait.style.display = 'none';

            if (loadingSection) loadingSection.style.display = 'none';
            if (statusMsg) statusMsg.style.display = 'none';
            renderAnalysisResults(results);
            if (resultsSection) resultsSection.style.display = 'grid';
            
            fetchHistory();

            isProcessing = false;
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            if (resumeSelect) resumeSelect.disabled = false;
            
            showToast("Resume analysis completed successfully.", "success");

        } catch (err) {
            clearInterval(countdownTimer);
            clearInterval(progressInterval);
            console.error(err);

            isProcessing = false;
            if (loadingSection) loadingSection.style.display = 'none';
            if (errorSection) errorSection.style.display = 'flex';
            if (statusMsg) statusMsg.style.display = 'none';
            
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            if (btnRetryAnalysis) btnRetryAnalysis.disabled = false;
            if (resumeSelect) resumeSelect.disabled = false;

            showAlert(err.message || "Unable to analyze resume.", 'danger');
            showToast(err.message || "Unable to analyze resume.", 'error');
        }
    };

    // Populate analysis view fields dynamically
    const renderAnalysisResults = (data) => {
        if (!data) return;

        // 1. Resume Summary
        const summaryEl = document.getElementById('res-summary') || document.getElementById('resume-summary');
        if (summaryEl) summaryEl.textContent = data.resume_summary || data.summary || 'N/A';

        // Badges helper
        const renderBadges = (elementId, list, typeClass) => {
            const container = document.getElementById(elementId);
            if (!container) return;
            container.innerHTML = '';
            if (list && list.length > 0) {
                list.forEach(item => {
                    const badge = document.createElement('span');
                    badge.className = `badge badge--${typeClass}`;
                    badge.textContent = item;
                    container.appendChild(badge);
                });
            } else {
                container.innerHTML = '<span style="color: var(--text-muted); font-size: 0.88rem;">None detected</span>';
            }
        };

        // 2. Technical Skills
        renderBadges('res-tech-skills', data.technical_skills || data.technical_skills_found, 'technical');
        renderBadges('technical-skills', data.technical_skills || data.technical_skills_found, 'technical');

        // 3. Soft Skills
        renderBadges('res-soft-skills', data.soft_skills || data.soft_skills_found, 'soft');
        renderBadges('soft-skills', data.soft_skills || data.soft_skills_found, 'soft');

        // Lists helper
        const renderListItems = (elementId, itemsList, prefixClass = '') => {
            const container = document.getElementById(elementId);
            if (!container) return;
            container.innerHTML = '';
            if (itemsList && itemsList.length > 0) {
                itemsList.forEach((text, idx) => {
                    const li = document.createElement('li');
                    if (elementId.includes('recommend') || elementId.includes('improvement')) {
                        li.className = 'rec-item';
                        li.innerHTML = `
                            <div class="rec-counter-num">${idx + 1}</div>
                            <div class="rec-text">${text}</div>
                        `;
                    } else {
                        li.className = `analysis-list-item ${prefixClass ? prefixClass + '-item' : ''}`;
                        li.textContent = text;
                    }
                    container.appendChild(li);
                });
            } else {
                container.innerHTML = `<li style="color: var(--text-muted); list-style: none; font-size: 0.88rem; padding-left: 0;">None reported</li>`;
            }
        };

        // 4. Strengths
        renderListItems('res-strengths', data.strengths, 'strength');
        renderListItems('strengths', data.strengths, 'strength');

        // 5. Weaknesses
        renderListItems('res-weaknesses', data.weaknesses, 'weakness');
        renderListItems('weaknesses', data.weaknesses, 'weakness');

        // 6. Actionable Recommendations
        const recs = data.improvements || data.actionable_recommendations || data.career_recommendations || [];
        renderListItems('res-recommendations', recs);
        renderListItems('improvements', recs);
        renderListItems('career-recommendations', recs);

        // Render Results Grid
        if (resultsSection) resultsSection.style.display = 'grid';
    };

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const resumeId = resumeSelect ? resumeSelect.value : null;
            if (resumeId) {
                runResumeAnalysis(resumeId);
            } else {
                showAlert("Please select a resume to analyze.", "danger");
            }
        });
    }

    if (resumeSelect) {
        resumeSelect.addEventListener('change', () => {
            if (resumeSelect.value && btnRunAnalysis) {
                btnRunAnalysis.disabled = false;
            }
        });
    }

    if (btnRunAnalysis) {
        btnRunAnalysis.addEventListener('click', (e) => {
            const resumeId = resumeSelect ? resumeSelect.value : null;
            if (resumeId) {
                runResumeAnalysis(resumeId);
            }
        });
    }

    if (btnRetryAnalysis) {
        btnRetryAnalysis.addEventListener('click', () => {
            const resumeId = resumeSelect ? resumeSelect.value : null;
            if (resumeId) {
                runResumeAnalysis(resumeId);
            }
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            loadResumes();
            fetchHistory();
        }

        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                loadResumes();
                fetchHistory();
            }
        });
    };

    init();
});
