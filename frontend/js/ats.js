import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunAts = document.getElementById('btn-run-ats');
    const form = document.getElementById('ats-grader-form');
    const resultsWrapper = document.getElementById('ats-results-wrapper');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No user is logged in.");
        return session.access_token;
    };

    const populateDropdown = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/resume/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const data = await res.json();

            resumeSelect.innerHTML = '<option value="" disabled selected>-- Select a Resume --</option>';
            if (data.length === 0) {
                resumeSelect.innerHTML = '<option value="" disabled>Please upload a resume first.</option>';
                return;
            }

            data.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.id;
                opt.textContent = `${item.filename} (Uploaded: ${new Date(item.uploaded_at).toLocaleDateString()})`;
                resumeSelect.appendChild(opt);
            });
            btnRunAts.disabled = false;
        } catch (err) {
            resumeSelect.innerHTML = '<option value="" disabled>Error loading resumes.</option>';
        }
    };

    const animateRings = (data) => {
        resultsWrapper.style.display = 'grid';

        // Animate overall score circle ring
        const overall = data.overall_score || 0;
        const ring = document.getElementById('overall-ring');
        const text = document.getElementById('overall-val');
        
        // Circumference of 70r circle is ~440
        const offset = 440 - (440 * overall) / 100;
        ring.style.strokeDashoffset = offset;
        text.textContent = `${overall}%`;

        // Sub scores
        const metrics = [
            { id: 'keyword', value: data.keyword_score },
            { id: 'format', value: data.format_score },
            { id: 'grammar', value: data.grammar_score },
            { id: 'experience', value: data.experience_score }
        ];

        metrics.forEach(m => {
            const valEl = document.getElementById(`val-${m.id}`);
            const fillEl = document.getElementById(`fill-${m.id}`);
            valEl.textContent = `${m.value || 0}%`;
            fillEl.style.width = `${m.value || 0}%`;
        });

        // Recommendations
        const recsList = document.getElementById('ats-recs-list');
        recsList.innerHTML = '';
        const recs = data.recommendations || [];
        if (recs.length === 0) {
            recsList.innerHTML = '<li>No adjustments recommended. Great job!</li>';
        } else {
            recs.forEach(rec => {
                const li = document.createElement('li');
                li.textContent = rec;
                recsList.appendChild(li);
            });
        }
    };

    const loadLatestScore = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/ats/latest`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                animateRings(data);
            }
        } catch (e) {
            // Ignore error if no record found
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const resumeId = resumeSelect.value;
        if (!resumeId) return;

        btnRunAts.disabled = true;
        btnRunAts.querySelector('span').textContent = 'Grading...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/ats/score`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ resume_id: resumeId })
            });

            if (!res.ok) throw new Error("Failed to calculate ATS score.");
            const data = await res.json();
            animateRings(data);
        } catch (err) {
            alert(err.message);
        } finally {
            btnRunAts.disabled = false;
            btnRunAts.querySelector('span').textContent = 'Calculate ATS Score';
        }
    });

    populateDropdown().then(loadLatestScore);
});