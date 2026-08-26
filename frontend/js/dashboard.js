import { supabase } from './supabaseClient.js';
import { getCurrentCareerGoal } from './careerGoal.js';
import { getCandidateProfile } from './candidateProfile.js';
import { getCurrentAssessment } from './assessment.js';
import { getCurrentLearningPlan } from './learningPlan.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const statAtsVal = document.getElementById('stat-ats-val');
    const statJobmatchVal = document.getElementById('stat-jobmatch-val');
    const statInterviewVal = document.getElementById('stat-interview-val');
    const statReadinessVal = document.getElementById('stat-readiness-val');

    // Career Goal DOM elements
    const goalLoading = document.getElementById('goal-content-loading');
    const goalLoaded = document.getElementById('goal-content-loaded');
    const goalEmpty = document.getElementById('goal-content-empty');
    const goalStatusBadge = document.getElementById('goal-status-badge');
    const goalCompanyVal = document.getElementById('goal-company-val');
    const goalRoleVal = document.getElementById('goal-role-val');
    const goalExpVal = document.getElementById('goal-exp-val');
    const goalLocVal = document.getElementById('goal-loc-val');
    const goalTimeVal = document.getElementById('goal-time-val');
    const btnEditGoal = document.getElementById('btn-edit-goal');
    const btnSetGoal = document.getElementById('btn-set-goal');

    // Candidate Profile DOM elements
    const profileBadge = document.getElementById('dash-profile-completeness-badge');
    const profileDesc = document.getElementById('dash-profile-status-desc');

    // Assessment Banner DOM elements
    const assessBadge = document.getElementById('dash-assessment-badge');
    const assessDesc = document.getElementById('dash-assessment-desc');

    // Learning Plan Banner DOM elements
    const planBadge = document.getElementById('dash-plan-progress-badge');
    const planDesc = document.getElementById('dash-plan-status-desc');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
    };

    // Load Learning Plan status
    const loadDashboardLearningPlan = async () => {
        try {
            const plan = await getCurrentLearningPlan();
            if (plan) {
                const prog = plan.overall_progress || 0;
                if (planBadge) {
                    planBadge.textContent = `${prog}% PROGRESS`;
                    if (prog > 0) {
                        planBadge.style.background = 'rgba(46, 125, 50, 0.12)';
                        planBadge.style.color = 'var(--success)';
                    }
                }
                if (planDesc && plan.plan_summary) {
                    planDesc.textContent = plan.plan_summary;
                }
            }
        } catch (err) {
            console.error("Error loading learning plan for dashboard:", err);
        }
    };

    // Load Assessment status
    const loadDashboardAssessment = async () => {
        try {
            const assess = await getCurrentAssessment();
            if (assess) {
                const readScore = assess.career_readiness_score || 0;
                const atsScore = assess.ats_score || 0;
                if (assessBadge) {
                    assessBadge.textContent = `${readScore}% READINESS`;
                    assessBadge.style.background = 'rgba(46, 125, 50, 0.12)';
                    assessBadge.style.color = 'var(--success)';
                }
                if (assessDesc) {
                    assessDesc.textContent = `Latest target match: ${atsScore}% ATS score for ${assess.target_company || 'Target'} ${assess.target_job_role || 'Role'}.`;
                }
                if (statReadinessVal) {
                    statReadinessVal.textContent = `${readScore}/100`;
                }
            }
        } catch (err) {
            console.error("Error loading assessment for dashboard:", err);
        }
    };

    // Load Candidate Profile widget
    const loadDashboardProfile = async () => {
        try {
            const profile = await getCandidateProfile();
            if (profile) {
                const score = profile.completeness || 0;
                if (profileBadge) {
                    profileBadge.textContent = `${score}% COMPLETE`;
                    if (score >= 80) {
                        profileBadge.style.background = 'rgba(46, 125, 50, 0.12)';
                        profileBadge.style.color = 'var(--success)';
                    } else if (score >= 40) {
                        profileBadge.style.background = 'rgba(230, 81, 0, 0.12)';
                        profileBadge.style.color = 'var(--warning)';
                    }
                }
                if (profileDesc) {
                    if (score >= 80) {
                        profileDesc.textContent = "Your profile is well detailed and ready for intelligent AI target company analysis.";
                    } else {
                        profileDesc.textContent = `Profile is ${score}% complete. Add your education, skills, and projects to unlock full AI guidance.`;
                    }
                }
            }
        } catch (err) {
            console.error("Error loading candidate profile for dashboard:", err);
        }
    };

    // Load Career Goal in dashboard widget
    const loadDashboardCareerGoal = async () => {
        try {
            const goal = await getCurrentCareerGoal();

            if (goalLoading) goalLoading.style.display = 'none';

            if (goal) {
                if (goalLoaded) goalLoaded.style.display = 'block';
                if (goalEmpty) goalEmpty.style.display = 'none';
                if (btnEditGoal) btnEditGoal.style.display = 'inline-flex';
                if (btnSetGoal) btnSetGoal.style.display = 'none';

                if (goalCompanyVal) goalCompanyVal.textContent = goal.company_name || '--';
                if (goalRoleVal) goalRoleVal.textContent = goal.job_role || '--';
                if (goalExpVal) goalExpVal.textContent = goal.experience_level || '--';
                if (goalLocVal) goalLocVal.textContent = goal.target_location || 'Flexible';
                if (goalTimeVal) goalTimeVal.textContent = goal.target_timeline || 'Flexible';
                if (goalStatusBadge) {
                    goalStatusBadge.textContent = (goal.status || 'ACTIVE').toUpperCase();
                    goalStatusBadge.style.display = 'inline-block';
                }
            } else {
                if (goalLoaded) goalLoaded.style.display = 'none';
                if (goalEmpty) goalEmpty.style.display = 'block';
                if (btnEditGoal) btnEditGoal.style.display = 'none';
                if (btnSetGoal) btnSetGoal.style.display = 'inline-flex';
                if (goalStatusBadge) goalStatusBadge.style.display = 'none';
            }
        } catch (err) {
            console.error("Error loading career goal for dashboard:", err);
            if (goalLoading) goalLoading.style.display = 'none';
            if (goalEmpty) goalEmpty.style.display = 'block';
            if (btnSetGoal) btnSetGoal.style.display = 'inline-flex';
        }
    };

    // Load real metrics across all modules
    const loadDashboardMetrics = async () => {
        try {
            const token = await getAuthToken();
            if (!token) return;

            const headers = { 'Authorization': `Bearer ${token}` };

            // 1. ATS Score
            try {
                const resATS = await fetch(`${API_BASE_URL}/api/ats/history`, { headers });
                if (resATS.ok) {
                    const atsList = await resATS.json();
                    if (Array.isArray(atsList) && atsList.length > 0) {
                        const topAts = atsList[0].ats_results ? (atsList[0].ats_results.overall_score || atsList[0].ats_score) : atsList[0].overall_score;
                        if (typeof topAts === 'number') {
                            statAtsVal.textContent = `${topAts}%`;
                        }
                    }
                }
            } catch (err) {
                console.error("Dashboard ATS load error:", err);
            }

            // 2. Job Match Score
            try {
                const resJM = await fetch(`${API_BASE_URL}/api/job-matching/history`, { headers });
                if (resJM.ok) {
                    const jmList = await resJM.json();
                    if (Array.isArray(jmList) && jmList.length > 0) {
                        const topJM = jmList[0].match_score ?? jmList[0].match_percentage;
                        if (typeof topJM === 'number') {
                            statJobmatchVal.textContent = `${topJM}%`;
                        }
                    }
                }
            } catch (err) {
                console.error("Dashboard Job Match load error:", err);
            }

            // 3. Interview Readiness
            try {
                const resInt = await fetch(`${API_BASE_URL}/api/interview/history`, { headers });
                if (resInt.ok) {
                    const intList = await resInt.json();
                    if (Array.isArray(intList) && intList.length > 0) {
                        const topInt = intList[0].overall_score;
                        if (typeof topInt === 'number') {
                            statInterviewVal.textContent = `${topInt}/100`;
                        }
                    }
                }
            } catch (err) {
                console.error("Dashboard Interview load error:", err);
            }

            // 4. Career Readiness
            try {
                const resRM = await fetch(`${API_BASE_URL}/api/career-roadmap`, { headers });
                if (resRM.ok) {
                    const rmList = await resRM.json();
                    if (Array.isArray(rmList) && rmList.length > 0) {
                        const topRM = rmList[0].readiness_score;
                        if (typeof topRM === 'number') {
                            statReadinessVal.textContent = `${topRM}/100`;
                        }
                    }
                }
            } catch (err) {
                console.error("Dashboard Roadmap load error:", err);
            }

        } catch (err) {
            console.error("Dashboard metrics initialization error:", err);
        }
    };

    loadDashboardCareerGoal();
    loadDashboardProfile();
    loadDashboardAssessment();
    loadDashboardLearningPlan();
    loadDashboardMetrics();
});