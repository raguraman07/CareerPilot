import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const statAtsVal = document.getElementById('stat-ats-val');
    const statJobmatchVal = document.getElementById('stat-jobmatch-val');
    const statInterviewVal = document.getElementById('stat-interview-val');
    const statReadinessVal = document.getElementById('stat-readiness-val');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return null;
        return session.access_token;
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

    loadDashboardMetrics();
});