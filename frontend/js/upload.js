/**
 * CareerPilot AI — Resume Upload Module Interactivity
 * Handles drag and drop events, file validations, XHR upload progress indicators,
 * resume list database fetches, deletions, and toast notifications.
 */

import { supabase } from './supabaseClient.js';

// Configuration: Matches the Flask backend API server base URL
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;
const ALLOWED_MIME_TYPES = ['.pdf', '.doc', '.docx'];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('resume-file-input') || document.getElementById('file-input');
    const browseFilesBtn = document.getElementById('browse-files-btn');
    const selectedFileCard = document.getElementById('selected-file-card');
    const selectedFilename = document.getElementById('selected-file-name') || document.getElementById('selected-filename');
    const selectedFilesize = document.getElementById('selected-file-size') || document.getElementById('selected-filesize');
    const fileIconWrapper = document.querySelector('.file-icon-box') || document.getElementById('file-icon-wrapper');
    const removeFileBtn = document.getElementById('btn-cancel-file') || document.getElementById('remove-file-btn');
    
    const progressWrapper = document.getElementById('upload-progress-wrapper');
    const progressFill = document.getElementById('progress-bar-fill');
    const progressPercent = document.getElementById('progress-percent-val');
    const progressStatus = document.getElementById('progress-status-label');
    
    const actionRow = document.getElementById('upload-action-row');
    const btnSubmitUpload = document.getElementById('btn-submit-upload');
    const successParseBanner = document.getElementById('success-parse-banner');
    const successParsePages = document.getElementById('success-parse-pages');
    
    const resumesTbody = document.getElementById('resumes-tbody');
    const btnRefreshResumes = document.getElementById('btn-refresh-resumes');
    const toastContainer = document.getElementById('toast-container');

    let selectedFile = null;

    // -------------------------------------------------------------
    // 1. Toast Notification Alerts System
    // -------------------------------------------------------------
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
        
        toast.innerHTML = `
            ${iconSvg}
            <span>${message}</span>
        `;
        
        toastContainer.appendChild(toast);
        
        // Remove element from DOM after exit animation finishes (total duration 5s)
        setTimeout(() => {
            toast.remove();
        }, 5000);
    };

    // Helper: Formats bytes to standard human readable string size
    const formatBytes = (bytes, decimals = 1) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    };

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    // -------------------------------------------------------------
    // 2. Drag & Drop Visual Event Triggers
    // -------------------------------------------------------------
    const preventDefaults = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    if (dropzone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.remove('dragover');
            }, false);
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt ? dt.files : null;
            if (files && files.length > 0) {
                handleFileSelection(files[0]);
            }
        });

        dropzone.addEventListener('click', (e) => {
            if (e.target && (e.target.id === 'browse-files-btn' || e.target.closest('#browse-files-btn'))) {
                return;
            }
            if (fileInput) fileInput.click();
        });

        dropzone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (fileInput) fileInput.click();
            }
        });
    }

    if (browseFilesBtn) {
        browseFilesBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (fileInput) fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }

    // -------------------------------------------------------------
    // 3. Client Side File Validation
    // -------------------------------------------------------------
    const handleFileSelection = (file) => {
        if (!file) return;

        // Reset state
        resetUploadState();

        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!ALLOWED_MIME_TYPES.includes(ext)) {
            showToast("Only PDF, DOC, and DOCX documents are allowed.", "error");
            return;
        }

        if (file.size > MAX_FILE_SIZE) {
            showToast("File size exceeds the maximum limit of 5 MB.", "error");
            return;
        }

        selectedFile = file;

        // Customise PDF / DOCX type icon colors
        if (fileIconWrapper) {
            if (ext === '.pdf') {
                fileIconWrapper.textContent = 'PDF';
                fileIconWrapper.style.color = '#E53935'; // PDF Red
                fileIconWrapper.style.backgroundColor = 'rgba(229, 57, 53, 0.08)';
            } else {
                fileIconWrapper.textContent = 'DOC';
                fileIconWrapper.style.color = '#1E88E5'; // Word Blue
                fileIconWrapper.style.backgroundColor = 'rgba(30, 136, 229, 0.08)';
            }
        }

        // Display selection visual elements
        if (selectedFilename) selectedFilename.textContent = file.name;
        if (selectedFilesize) selectedFilesize.textContent = formatBytes(file.size);
        if (selectedFileCard) selectedFileCard.style.display = 'flex';
        if (actionRow) actionRow.style.display = 'block';
        if (btnSubmitUpload) btnSubmitUpload.disabled = false;
        
        showToast(`Selected file: ${file.name}`, "info");
    };

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            resetUploadState();
        });
    }

    const resetUploadState = () => {
        selectedFile = null;
        if (fileInput) fileInput.value = '';
        if (selectedFileCard) selectedFileCard.style.display = 'none';
        if (progressWrapper) progressWrapper.style.display = 'none';
        if (actionRow) actionRow.style.display = 'none';
        if (successParseBanner) successParseBanner.style.display = 'none';
        
        // Reset progress bar trackers
        if (progressFill) progressFill.style.width = '0%';
        if (progressPercent) progressPercent.textContent = '0%';
    };

    const uploadForm = document.getElementById('resume-upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (btnSubmitUpload) btnSubmitUpload.click();
        });
    }

    if (btnSubmitUpload) {
        btnSubmitUpload.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!selectedFile) return;

        // Initialize progress view states
        progressWrapper.style.display = 'block';
        actionRow.style.display = 'none';
        btnSubmitUpload.disabled = true;
        
        progressStatus.textContent = "Uploading resume to secure storage...";
        progressFill.style.width = '0%';
        progressPercent.textContent = '0%';

        try {
            const token = await getAuthToken();
            const formData = new FormData();
            formData.append('file', selectedFile);

            const xhr = new XMLHttpRequest();
            
            // XHR Upload Progress Event Handlers
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    // Cap upload percent at 95% until server returns complete parse response
                    const displayedPercent = Math.min(percent, 95);
                    progressFill.style.width = `${displayedPercent}%`;
                    progressPercent.textContent = `${displayedPercent}%`;
                    
                    if (percent >= 100) {
                        progressStatus.textContent = "Extracting text structure and content elements...";
                    }
                }
            });

            // XHR Response Handlers
            xhr.addEventListener('load', () => {
                btnSubmitUpload.disabled = false;
                
                if (xhr.status === 201) {
                    const res = JSON.parse(xhr.responseText);
                    progressFill.style.width = '100%';
                    progressPercent.textContent = '100%';
                    progressStatus.textContent = "Parsing completed successfully.";
                    
                    // Show success checkmark animations and redirect to analysis
                    setTimeout(() => {
                        selectedFileCard.style.display = 'none';
                        progressWrapper.style.display = 'none';
                        
                        showToast("Resume successfully uploaded! Redirecting to AI Analysis...", "success");
                        
                        setTimeout(() => {
                            window.location.href = `analysis.html?resume_id=${res.id}&auto_analyze=true`;
                        }, 1200);
                    }, 500);
                    
                } else {
                    let errMsg = "Failed to upload or parse resume file.";
                    try {
                        const errObj = JSON.parse(xhr.responseText);
                        errMsg = errObj.error || errMsg;
                    } catch (_) {}
                    
                    showToast(errMsg, "error");
                    progressWrapper.style.display = 'none';
                    actionRow.style.display = 'block';
                }
            });

            xhr.addEventListener('error', () => {
                btnSubmitUpload.disabled = false;
                showToast("Network connection error during file upload.", "error");
                progressWrapper.style.display = 'none';
                actionRow.style.display = 'block';
            });

            xhr.open('POST', `${API_BASE_URL}/api/resume/upload`);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            xhr.send(formData);

        } catch (authErr) {
            btnSubmitUpload.disabled = false;
            showToast("Failed to authenticate session token: " + authErr.message, "error");
            progressWrapper.style.display = 'none';
            actionRow.style.display = 'block';
        }
    });
    }

    // -------------------------------------------------------------
    // 5. Database listing fetch and render table logs
    // -------------------------------------------------------------
    const fetchUploadedResumes = async () => {
        if (!resumesTbody) return;
        
        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errObj = await response.json();
                throw new Error(errObj.error || "Failed to retrieve resumes list.");
            }

            const list = await response.json();
            renderResumesList(list);
            
        } catch (e) {
            console.error("Listing fetch error:", e);
            resumesTbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        Failed to load resume database logs. Verify local server backend connection.
                    </td>
                </tr>
            `;
        }
    };

    const renderResumesList = (resumes) => {
        if (resumes.length === 0) {
            resumesTbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                        No uploaded resumes found.
                    </td>
                </tr>
            `;
            return;
        }

        resumesTbody.innerHTML = resumes.map(r => {
            const uploadDate = new Date(r.uploaded_at).toLocaleString();
            const badgeClass = r.status === 'parsed' ? 'success' : 'info';
            const iconSvg = r.file_type === 'pdf' 
                ? `<svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:#E53935;" class="pill-svg"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>` 
                : `<svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:#1E88E5;" class="pill-svg"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;
            
            return `
                <tr data-id="${r.id}">
                    <td class="activity-col">
                        <span style="display:flex;align-items:center;gap:0.5rem;">
                            ${iconSvg}
                            <span>${r.filename}</span>
                        </span>
                    </td>
                    <td><span class="dropzone-info-badge">${r.file_type}</span></td>
                    <td class="mono-figure">${r.pages}</td>
                    <td class="date-col">${uploadDate}</td>
                    <td><span class="status-badge ${badgeClass}">${r.status}</span></td>
                    <td style="text-align: right;">
                        <button class="action-icon-btn btn-delete-resume" data-id="${r.id}" aria-label="Delete resume ${r.filename}">
                            <svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // Attach event listeners for delete actions
        resumesTbody.querySelectorAll('.btn-delete-resume').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                const row = btn.closest('tr');
                const filename = row.querySelector('.activity-col span span').textContent;
                
                if (confirm(`Are you sure you want to permanently delete the resume "${filename}"?`)) {
                    deleteResume(id, row, filename);
                }
            });
        });
    };

    // -------------------------------------------------------------
    // 6. Delete Action Handling
    // -------------------------------------------------------------
    const deleteResume = async (id, rowElement, filename) => {
        try {
            const token = await getAuthToken();
            const response = await fetch(`${API_BASE_URL}/api/resume/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errObj = await response.json();
                throw new Error(errObj.error || "Failed to delete the resume.");
            }

            // Remove visual element from table with fade transition
            rowElement.style.transition = 'opacity var(--transition-fast)';
            rowElement.style.opacity = '0';
            setTimeout(() => {
                rowElement.remove();
                
                // If table is now empty, render empty state
                if (resumesTbody.children.length === 0) {
                    resumesTbody.innerHTML = `
                        <tr>
                            <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                                No uploaded resumes found.
                            </td>
                        </tr>
                    `;
                }
            }, 300);

            showToast(`Deleted resume: ${filename}`, "success");

        } catch (e) {
            console.error("Delete request error:", e);
            showToast("Failed to delete resume: " + e.message, "error");
        }
    };

    btnRefreshResumes.addEventListener('click', () => {
        // Simple spin animations
        const refreshSvg = btnRefreshResumes.querySelector('svg');
        if (refreshSvg) {
            refreshSvg.style.transition = 'transform 0.8s ease';
            refreshSvg.style.transform = 'rotate(360deg)';
            setTimeout(() => {
                refreshSvg.style.transition = 'none';
                refreshSvg.style.transform = 'rotate(0)';
            }, 800);
        }
        
        fetchUploadedResumes();
    });

    // Check Supabase authentication state changes on load to run listing fetch
    supabase.auth.onAuthStateChange((event, session) => {
        if (session) {
            fetchUploadedResumes();
        }
    });
});