/**
 * CareerPilot AI — Resume Analysis Interactivity
 * Handles loading list of resumes, triggering AI review, progress animations,
 * updating the UI card elements, loading history, and firing success/error toast notifications.
 */

import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunAnalysis = document.getElementById('btn-run-analysis');
    const btnRetryAnalysis = document.getElementById('btn-retry-analysis');
    
    const loadingSection = document.getElementById('analysis-loading');
    const errorSection = document.getElementById('analysis-error');
    const progressFill = document.getElementById('progress-fill');
    const progressStatus = document.getElementById('progress-status');
    const estimatedWait = document.getElementById('estimated-wait');
    
    const resultsSection = document.getElementById('analysis-results');
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
            iconSvg = `<svg class="toast-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="8"></line></svg>`;
        }
        
        toast.innerHTML = `${iconSvg}<span>${message}</span>`;
        toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    };

    // Helper: Fetch authorization bearer token
    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No user is logged in.");
        return session.access_token;
    };

    // Load available resumes to populate the dropdown
    const loadResumes = async () => {
        const selectContainer = document.getElementById('resume-select-container');
        if (btnRunAnalysis) btnRunAnalysis.disabled = true;

        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error("Failed to load your resumes list.");
            }

            const data = await response.json();
            
            if (!Array.isArray(data) || data.length === 0) {
                if (selectContainer) {
                    selectContainer.innerHTML = `
                        <div class="resume-selector-card">
                            <div class="resume-selector-left">
                                <div class="resume-selector-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                        <polyline points="14 2 14 8 20 8"></polyline>
                                    </svg>
                                </div>
                                <div class="resume-selector-text">
                                    <div class="resume-selector-title">No resumes uploaded yet</div>
                                    <div class="resume-selector-subtitle">Please upload a resume first to run AI analysis.</div>
                                </div>
                            </div>
                            <div class="resume-selector-right">
                                <a href="upload.html" class="btn btn-primary btn-sm">Upload Resume</a>
                            </div>
                        </div>
                    `;
                }
                if (resumeSelect) resumeSelect.style.display = 'none';
                if (btnRunAnalysis) btnRunAnalysis.disabled = true;
                return;
            }

            resumeSelect.innerHTML = '<option value="" disabled selected>-- Select an Uploaded Resume --</option>';
            data.forEach(res => {
                const opt = document.createElement('option');
                opt.value = res.id;
                opt.textContent = `${res.filename} ${res.uploaded_at ? `(Uploaded: ${new Date(res.uploaded_at).toLocaleDateString()})` : ''}`;
                resumeSelect.appendChild(opt);
            });

            // Resumes Loaded: Hide loading container & show custom select box
            if (selectContainer) selectContainer.style.display = 'none';
            if (resumeSelect) resumeSelect.style.display = 'block';

            // Enable submit button when a valid resume is selected
            const checkSelection = () => {
                if (btnRunAnalysis) btnRunAnalysis.disabled = !resumeSelect.value;
            };
            resumeSelect.addEventListener('change', checkSelection);
            checkSelection();

            // After loading resumes, check if resume_id URL query parameter exists
            checkUrlQueryParams();

        } catch (err) {
            console.error(err);
            showToast(err.message, 'error');
            if (selectContainer) {
                selectContainer.innerHTML = `
                    <div class="resume-selector-card">
                        <div class="resume-selector-left">
                            <div class="resume-selector-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <line x1="12" y1="8" x2="12" y2="12"></line>
                                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                                </svg>
                            </div>
                            <div class="resume-selector-text">
                                <div class="resume-selector-title">Error loading resumes</div>
                                <div class="resume-selector-subtitle">Please check your connection and reload the page.</div>
                            </div>
                        </div>
                    </div>
                `;
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
            historyList.innerHTML = `<li style="padding: 1rem; text-align: center; color: var(--error-color); font-size: 0.82rem;">Failed to load history list</li>`;
        }
    };

    const renderHistoryList = (list) => {
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

        // Add click listener to select a historical record
        historyList.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                // Clear active status on all list elements
                historyList.querySelectorAll('.history-item').forEach(x => x.classList.remove('active'));
                el.classList.add('active');

                const analysisId = el.getAttribute('data-id');
                const matched = list.find(x => x.id === analysisId);
                
                if (matched && matched.analysis_results) {
                    // Update dropdown selection if possible
                    if (matched.resume_id) {
                        resumeSelect.value = matched.resume_id;
                        btnRunAnalysis.disabled = false;
                    }
                    
                    // Render historical insights instantly
                    errorSection.style.display = 'none';
                    loadingSection.style.display = 'none';
                    renderAnalysisResults(matched.analysis_results);
                    resultsSection.style.display = 'block';
                    
                    showToast("Loaded analysis from history cache.", "info");
                }
            });
        });
    };

    // Check if the URL has parameter inputs to trigger automatic run
    const checkUrlQueryParams = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const resumeId = urlParams.get('resume_id');
        const autoAnalyze = urlParams.get('auto_analyze') === 'true';

        if (resumeId) {
            // Select in dropdown
            resumeSelect.value = resumeId;
            btnRunAnalysis.disabled = false;
            
            if (autoAnalyze) {
                // Automatically run
                runResumeAnalysis(resumeId);
            }
        }
    };

    // Run Analysis Flow
    const runResumeAnalysis = async (resumeId) => {
        if (isProcessing) return;
        isProcessing = true;

        // Visual State Transitions
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';
        loadingSection.style.display = 'flex';
        estimatedWait.style.display = 'block';
        
        btnRunAnalysis.disabled = true;
        btnRetryAnalysis.disabled = true;
        resumeSelect.disabled = true;

        // Estimated wait countdown timer (starts around 5 seconds)
        let secondsLeft = 5;
        estimatedWait.textContent = `Estimated wait time: ~${secondsLeft} seconds...`;
        const countdownTimer = setInterval(() => {
            if (secondsLeft > 1) {
                secondsLeft--;
                estimatedWait.textContent = `Estimated wait time: ~${secondsLeft} seconds...`;
            } else {
                estimatedWait.textContent = `Wrapping up analysis details...`;
                clearInterval(countdownTimer);
            }
        }, 1000);

        // Progress bar simulation updates
        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 90) {
                progress += Math.floor(Math.random() * 15) + 5;
                if (progress > 90) progress = 90;
                progressFill.style.width = `${progress}%`;
                
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
        }, 400);

        try {
            const token = await getAuthToken();
            
            // Post to analysis API endpoint
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

            progressFill.style.width = '100%';
            progressStatus.textContent = "Resume analysis completed successfully.";
            estimatedWait.style.display = 'none';

            // Show results
            setTimeout(() => {
                loadingSection.style.display = 'none';
                renderAnalysisResults(results);
                resultsSection.style.display = 'block';
                
                // Refresh list history log
                fetchHistory();

                isProcessing = false;
                btnRunAnalysis.disabled = false;
                resumeSelect.disabled = false;
                
                showToast("Resume analysis completed successfully.", "success");
            }, 600);

        } catch (err) {
            clearInterval(countdownTimer);
            clearInterval(progressInterval);
            console.error(err);

            isProcessing = false;
            loadingSection.style.display = 'none';
            errorSection.style.display = 'flex';
            
            btnRunAnalysis.disabled = false;
            btnRetryAnalysis.disabled = false;
            resumeSelect.disabled = false;

            showToast(err.message || "Unable to analyze resume.", 'error');
            showToast("Analysis failed to complete.", 'error');
        }
    };

    // Populate analysis view fields dynamically
    const renderAnalysisResults = (data) => {
        // 1. Resume Summary
        document.getElementById('resume-summary').textContent = data.resume_summary || 'N/A';

        // Badges helper
        const renderBadges = (containerId, list, typeClass) => {
            const container = document.getElementById(containerId);
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
        renderBadges('technical-skills', data.technical_skills, 'technical');

        // 3. Soft Skills
        renderBadges('soft-skills', data.soft_skills, 'soft');

        // Lists helper
        const renderListItems = (containerId, itemsList, prefixClass = '') => {
            const container = document.getElementById(containerId);
            container.innerHTML = '';
            if (itemsList && itemsList.length > 0) {
                itemsList.forEach((text, idx) => {
                    const li = document.createElement('li');
                    if (containerId === 'improvements' || containerId === 'career-recommendations') {
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
        renderListItems('strengths', data.strengths, 'strength');

        // 5. Weaknesses
        renderListItems('weaknesses', data.weaknesses, 'weakness');

        // 6. Missing Skills
        renderBadges('missing-skills', data.missing_skills, 'missing');

        // 7. Recommended Roles
        renderBadges('recommended-roles', data.recommended_roles, 'technical');

        // 8. Improvement Suggestions
        renderListItems('improvements', data.improvements);

        // 9. Career Recommendations
        renderListItems('career-recommendations', data.career_recommendations);
    };

    // Selection changes listener
    resumeSelect.addEventListener('change', () => {
        if (resumeSelect.value) {
            btnRunAnalysis.disabled = false;
        }
    });

    // Run AI analysis manually
    btnRunAnalysis.addEventListener('click', () => {
        const resumeId = resumeSelect.value;
        if (resumeId) {
            runResumeAnalysis(resumeId);
        }
    });

    // Retry button click listener
    btnRetryAnalysis.addEventListener('click', () => {
        const resumeId = resumeSelect.value;
        if (resumeId) {
            runResumeAnalysis(resumeId);
        }
    });

    // Initialize list load once auth is completed
    const init = () => {
        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                loadResumes();
                fetchHistory();
            }
        });
    };

    init();
});
