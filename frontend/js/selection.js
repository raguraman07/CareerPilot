/**
 * CareerPilot AI — Interactive Selection Components Utility
 * Unified component manager for single-select cards, multi-select cards,
 * radio choice groups, dropdown sync, loading skeletons, empty & error states.
 */

// Helper to create checkmark SVG
const getCheckSvg = () => `
    <svg viewBox="0 0 24 24">
        <polyline points="20 6 9 17 4 12"></polyline>
    </svg>
`;

// Helper to create document icon SVG
const getDocumentSvg = () => `
    <svg viewBox="0 0 24 24">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
    </svg>
`;

// Helper to create folder/box empty SVG
const getEmptySvg = () => `
    <svg viewBox="0 0 24 24" width="22" height="22" stroke="var(--secondary)" fill="none" stroke-width="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
    </svg>
`;

// Helper to create alert error SVG
const getErrorSvg = () => `
    <svg viewBox="0 0 24 24" width="22" height="22" stroke="var(--danger)" fill="none" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
`;

/**
 * Render Skeleton Loading State Cards
 */
export const renderSelectionSkeleton = (container, count = 1, text = "Loading options...") => {
    if (!container) return;
    let html = '';
    for (let i = 0; i < count; i++) {
        html += `
            <div class="selection-skeleton" aria-label="${text}">
                <div class="skeleton-icon"></div>
                <div class="skeleton-lines">
                    <div class="skeleton-line long"></div>
                    <div class="skeleton-line short"></div>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
};

/**
 * Render Empty State Card
 */
export const renderSelectionEmpty = (container, message = "No options available", actionText = "+ Upload Resume", actionHref = "upload.html") => {
    if (!container) return;
    container.innerHTML = `
        <div class="selection-empty">
            <div class="selection-card-left">
                <div class="selection-card-icon" style="background-color: var(--surface-secondary); color: var(--secondary);">
                    ${getEmptySvg()}
                </div>
                <div class="selection-card-text">
                    <div class="selection-card-title">${message}</div>
                    <div class="selection-card-sub">Please add or upload options to continue.</div>
                </div>
            </div>
            ${actionText ? `
                <div class="selection-card-right">
                    <a href="${actionHref}" class="btn btn-primary btn-sm">${actionText}</a>
                </div>
            ` : ''}
        </div>
    `;
};

/**
 * Render Error State Card with Retry Action
 */
export const renderSelectionError = (container, message = "Couldn't load options", onRetry = null) => {
    if (!container) return;
    const errorId = `retry-btn-${Math.random().toString(36).substr(2, 9)}`;
    container.innerHTML = `
        <div class="selection-error">
            <div class="selection-card-left">
                <div class="selection-card-icon" style="background-color: var(--danger-light); color: var(--danger);">
                    ${getErrorSvg()}
                </div>
                <div class="selection-card-text">
                    <div class="selection-card-title">${message}</div>
                    <div class="selection-card-sub">Check your connection and try again.</div>
                </div>
            </div>
            <div class="selection-card-right">
                <button type="button" class="btn btn-outline btn-sm" id="${errorId}">Try again</button>
            </div>
        </div>
    `;
    if (onRetry) {
        setTimeout(() => {
            const btn = document.getElementById(errorId);
            if (btn) btn.addEventListener('click', onRetry);
        }, 0);
    }
};

/**
 * Render Interactive Resume Selection Cards synced with a hidden <select>
 */
export const renderResumeCards = (container, selectElement, resumes = [], onSelectCallback = null) => {
    if (!container || !selectElement) return;

    if (!Array.isArray(resumes) || resumes.length === 0) {
        renderSelectionEmpty(container, "No resumes uploaded yet", "+ Upload Resume", "upload.html");
        selectElement.innerHTML = '<option value="" disabled selected>-- No Resumes Found --</option>';
        selectElement.value = '';
        if (onSelectCallback) onSelectCallback('');
        return;
    }

    // Populate the hidden <select> to ensure native form behavior
    selectElement.innerHTML = '<option value="" disabled>-- Select a Resume --</option>';
    resumes.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        const uploadDate = r.uploaded_at ? new Date(r.uploaded_at).toLocaleDateString() : '';
        opt.textContent = `${r.filename}${uploadDate ? ` (${uploadDate})` : ''}`;
        selectElement.appendChild(opt);
    });

    // Auto-select first resume if current value is invalid or empty
    let selectedId = selectElement.value || resumes[0].id;
    selectElement.value = selectedId;

    // Render interactive cards container
    const isGrid = resumes.length > 2;
    const listWrapper = document.createElement('div');
    listWrapper.className = isGrid ? 'selection-grid' : 'selection-grid-single';

    resumes.forEach(r => {
        const isSelected = r.id === selectedId;
        const card = document.createElement('div');
        card.className = `selection-card ${isSelected ? 'is-selected' : ''}`;
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'option');
        card.setAttribute('aria-selected', isSelected ? 'true' : 'false');
        card.dataset.id = r.id;

        const uploadDateStr = r.uploaded_at ? `Uploaded ${new Date(r.uploaded_at).toLocaleDateString()}` : 'Uploaded recently';

        card.innerHTML = `
            <div class="selection-card-left">
                <div class="selection-card-icon">
                    ${getDocumentSvg()}
                </div>
                <div class="selection-card-text">
                    <div class="selection-card-title">${r.filename || 'Untitled Resume.pdf'}</div>
                    <div class="selection-card-sub">${uploadDateStr}</div>
                </div>
            </div>
            <div class="selection-card-right">
                <div class="selection-check-badge">
                    ${getCheckSvg()}
                </div>
            </div>
        `;

        const selectCard = () => {
            listWrapper.querySelectorAll('.selection-card').forEach(c => {
                c.classList.remove('is-selected');
                c.setAttribute('aria-selected', 'false');
            });
            card.classList.add('is-selected');
            card.setAttribute('aria-selected', 'true');

            selectElement.value = r.id;
            selectElement.dispatchEvent(new Event('change', { bubbles: true }));

            if (onSelectCallback) onSelectCallback(r.id);
        };

        card.addEventListener('click', selectCard);
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectCard();
            }
        });

        listWrapper.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(listWrapper);

    if (onSelectCallback) onSelectCallback(selectedId);
};

/**
 * Render Interactive Radio Choice Cards (Single Selection)
 */
export const renderRadioChoiceCards = (container, options = [], selectedValue = '', onChange = null) => {
    if (!container || !Array.isArray(options)) return;

    let currentVal = selectedValue || (options[0] ? options[0].value : '');
    const listWrapper = document.createElement('div');
    listWrapper.className = 'selection-grid';

    options.forEach(opt => {
        const isSelected = opt.value === currentVal;
        const card = document.createElement('div');
        card.className = `selection-card radio-card ${isSelected ? 'is-selected' : ''}`;
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'radio');
        card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        card.dataset.value = opt.value;

        const iconHtml = opt.iconSvg ? `
            <div class="selection-card-icon">
                ${opt.iconSvg}
            </div>
        ` : '';

        card.innerHTML = `
            <div class="selection-card-left">
                ${iconHtml}
                <div class="selection-card-text">
                    <div class="selection-card-title">${opt.label}</div>
                    ${opt.description ? `<div class="selection-card-sub">${opt.description}</div>` : ''}
                </div>
            </div>
            <div class="selection-card-right">
                <div class="selection-radio-dot"></div>
            </div>
        `;

        const selectChoice = () => {
            listWrapper.querySelectorAll('.radio-card').forEach(c => {
                c.classList.remove('is-selected');
                c.setAttribute('aria-checked', 'false');
            });
            card.classList.add('is-selected');
            card.setAttribute('aria-checked', 'true');
            currentVal = opt.value;
            if (onChange) onChange(opt.value);
        };

        card.addEventListener('click', selectChoice);
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectChoice();
            }
        });

        listWrapper.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(listWrapper);
};

// Global attachment for convenience in standard script tags
if (typeof window !== 'undefined') {
    window.CareerPilotSelection = {
        renderSelectionSkeleton,
        renderSelectionEmpty,
        renderSelectionError,
        renderResumeCards,
        renderRadioChoiceCards
    };
}
