// CareerPilot AI — Assessment Result & Review Client Module (Phase 5)
import { getAssessmentResult } from './knowledgeAssessment.js';

document.addEventListener('DOMContentLoaded', async () => {
    const resultPage = document.getElementById('assessment-result-page');
    if (!resultPage) return;

    const urlParams = new URLSearchParams(window.location.search);
    const assessmentId = urlParams.get('assessment_id');

    // DOM Elements
    const skillTitleEl = document.getElementById('res-skill-title');
    const roleSubtitleEl = document.getElementById('res-role-subtitle');
    const scoreValEl = document.getElementById('res-score-value');
    const statusBadgeEl = document.getElementById('res-status-badge');
    const skillLevelValEl = document.getElementById('res-level-value');
    const recommendationTextEl = document.getElementById('res-recommendation-text');
    const nextStepTextEl = document.getElementById('res-next-step-text');
    
    const strengthsContainerEl = document.getElementById('res-strengths-list');
    const weakAreasContainerEl = document.getElementById('res-weak-list');
    const reviewAccordionEl = document.getElementById('res-review-accordion');
    const btnRetakeEl = document.getElementById('btn-retake-test');

    if (!assessmentId) {
        if (recommendationTextEl) recommendationTextEl.textContent = "No assessment ID provided.";
        return;
    }

    try {
        const result = await getAssessmentResult(assessmentId);
        if (!result) {
            if (recommendationTextEl) recommendationTextEl.textContent = "Unable to load evaluation details.";
            return;
        }

        if (skillTitleEl) skillTitleEl.textContent = result.skill_name || 'Skill';
        if (roleSubtitleEl) roleSubtitleEl.textContent = `Evaluation for ${result.target_role || 'Role'} at ${result.target_company || 'Company'}`;
        if (scoreValEl) scoreValEl.textContent = `${result.score || 0}%`;
        if (skillLevelValEl) skillLevelValEl.textContent = result.skill_level || 'INTERMEDIATE';

        const isPassed = result.passed || result.score >= 75;
        if (statusBadgeEl) {
            statusBadgeEl.textContent = isPassed ? "PASSED ✓" : "NEEDS IMPROVEMENT ⚠";
            statusBadgeEl.style.background = isPassed ? "rgba(46, 125, 50, 0.15)" : "rgba(230, 81, 0, 0.15)";
            statusBadgeEl.style.color = isPassed ? "#2e7d32" : "#e65100";
            statusBadgeEl.style.border = `1px solid ${isPassed ? '#2e7d32' : '#e65100'}`;
        }

        if (recommendationTextEl) recommendationTextEl.textContent = result.recommendation || "";
        if (nextStepTextEl) nextStepTextEl.textContent = result.next_step || "";

        // Retake Link
        if (btnRetakeEl) {
            btnRetakeEl.href = `knowledge-assessment.html?skill_name=${encodeURIComponent(result.skill_name)}`;
        }

        // Strengths
        if (strengthsContainerEl) {
            strengthsContainerEl.innerHTML = '';
            (result.strengths || []).forEach(st => {
                const pill = document.createElement('span');
                pill.style.cssText = 'display: inline-block; padding: 0.35rem 0.85rem; background: rgba(46, 125, 50, 0.12); color: #2e7d32; border: 1px solid rgba(46, 125, 50, 0.3); border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 600;';
                pill.textContent = `✓ ${st}`;
                strengthsContainerEl.appendChild(pill);
            });
            if (!result.strengths || result.strengths.length === 0) {
                strengthsContainerEl.innerHTML = '<span style="color:var(--text-secondary); font-size:0.85rem; font-style:italic;">No confirmed strength areas in this attempt.</span>';
            }
        }

        // Weak Areas
        if (weakAreasContainerEl) {
            weakAreasContainerEl.innerHTML = '';
            (result.weak_areas || []).forEach(wk => {
                const pill = document.createElement('span');
                pill.style.cssText = 'display: inline-block; padding: 0.35rem 0.85rem; background: rgba(198, 40, 40, 0.12); color: #c62828; border: 1px solid rgba(198, 40, 40, 0.3); border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 600;';
                pill.textContent = `⚠ ${wk}`;
                weakAreasContainerEl.appendChild(pill);
            });
            if (!result.weak_areas || result.weak_areas.length === 0) {
                weakAreasContainerEl.innerHTML = '<span style="color:var(--text-secondary); font-size:0.85rem; font-style:italic;">None! All evaluated concepts met target criteria.</span>';
            }
        }

        // Question-by-Question Review
        if (reviewAccordionEl) {
            reviewAccordionEl.innerHTML = '';
            (result.question_results || []).forEach((qr, idx) => {
                const qCard = document.createElement('div');
                qCard.style.cssText = `background: var(--surface); border: 1px solid var(--border-light); border-left: 4px solid ${qr.is_correct ? '#2e7d32' : '#c62828'}; border-radius: var(--radius-md); padding: 1.25rem; margin-bottom: 1rem;`;

                qCard.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.8rem; font-weight: 700; color: var(--text-secondary);">Question ${idx + 1} (${escapeHtml(qr.topic || 'General')})</span>
                        <span style="font-size: 0.8rem; font-weight: 700; color: ${qr.is_correct ? '#2e7d32' : '#c62828'}; background: ${qr.is_correct ? 'rgba(46,125,50,0.1)' : 'rgba(198,40,40,0.1)'}; padding: 0.2rem 0.55rem; border-radius: 4px;">
                            ${qr.is_correct ? 'CORRECT (+10)' : `SCORE: ${qr.points_earned || 0}/10`}
                        </span>
                    </div>

                    <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.75rem 0;">${escapeHtml(qr.question)}</h4>

                    <div style="background: var(--surface-secondary); padding: 0.85rem 1rem; border-radius: var(--radius-sm); margin-bottom: 0.75rem; font-size: 0.88rem;">
                        <div style="margin-bottom: 0.35rem;">
                            <strong style="color: var(--text-secondary);">Your Answer:</strong>
                            <span style="color: ${qr.is_correct ? '#2e7d32' : '#c62828'}; font-weight: 600;"> ${escapeHtml(qr.user_answer || 'No answer provided')}</span>
                        </div>
                        ${!qr.is_correct && qr.correct_answer ? `
                        <div>
                            <strong style="color: var(--text-secondary);">Expected / Correct Answer:</strong>
                            <span style="color: #2e7d32; font-weight: 600;"> ${escapeHtml(qr.correct_answer)}</span>
                        </div>` : ''}
                        ${qr.feedback ? `
                        <div style="margin-top: 0.35rem; color: var(--text-primary);">
                            <strong style="color: var(--text-secondary);">Evaluator Feedback:</strong> ${escapeHtml(qr.feedback)}
                        </div>` : ''}
                        ${qr.missing_concepts && qr.missing_concepts.length > 0 ? `
                        <div style="margin-top: 0.35rem; color: #c62828;">
                            <strong>Missing Concepts:</strong> ${escapeHtml(qr.missing_concepts.join(', '))}
                        </div>` : ''}
                    </div>

                    ${qr.explanation ? `
                    <div style="font-size: 0.84rem; color: var(--text-secondary); line-height: 1.45;">
                        <strong style="color: var(--text-primary);">Concept Explanation:</strong> ${escapeHtml(qr.explanation)}
                    </div>` : ''}
                `;

                reviewAccordionEl.appendChild(qCard);
            });
        }

    } catch (err) {
        console.error("Error loading assessment result:", err);
    }
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
