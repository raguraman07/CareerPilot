import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunMatch = document.getElementById('btn-run-match');
    const form = document.getElementById('job-match-form');
    const resultsWrapper = document.getElementById('match-results-wrapper');
    const jobDescInput = document.getElementById('job-desc');

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
            btnRunMatch.disabled = false;
        } catch (err) {
            resumeSelect.innerHTML = '<option value="" disabled>Error loading resumes.</option>';
        }
    };

    const displayMatchDetails = (data) => {
        resultsWrapper.style.display = 'grid';

        const matchPct = data.match_percentage || 0;
        const ring = document.getElementById('match-ring');
        const textVal = document.getElementById('match-pct-val');
        const qualityDesc = document.getElementById('match-quality-desc');

        // Circumference of 45r circle is ~283
        const offset = 283 - (283 * matchPct) / 100;
        ring.style.strokeDashoffset = offset;
        textVal.textContent = `${matchPct}%`;

        // Match description text
        if (matchPct >= 80) {
            qualityDesc.textContent = "Excellent Match! Your skills match recruiters' main requirements.";
            ring.style.stroke = "#10b981";
        } else if (matchPct >= 60) {
            qualityDesc.textContent = "Good Potential. Some minor skill adjustments could optimize alignment.";
            ring.style.stroke = "#f59e0b";
        } else {
            qualityDesc.textContent = "High Skill Gap. Incorporate target skills in your experience details.";
            ring.style.stroke = "#ef4444";
        }

        // Matching skills
        const matchContainer = document.getElementById('match-skills-badges');
        matchContainer.innerHTML = '';
        const matching = data.matching_skills || [];
        if (matching.length === 0) {
            matchContainer.innerHTML = '<span style="color:var(--text-muted);font-size:0.87rem;">No matched skills found.</span>';
        } else {
            matching.forEach(skill => {
                const span = document.createElement('span');
                span.className = 'skill-badge match';
                span.textContent = skill;
                matchContainer.appendChild(span);
            });
        }

        // Missing skills
        const missingContainer = document.getElementById('missing-skills-badges');
        missingContainer.innerHTML = '';
        const missing = data.missing_skills || [];
        if (missing.length === 0) {
            missingContainer.innerHTML = '<span style="color:var(--text-muted);font-size:0.87rem;">No skill gaps identified!</span>';
        } else {
            missing.forEach(skill => {
                const span = document.createElement('span');
                span.className = 'skill-badge missing';
                span.textContent = skill;
                missingContainer.appendChild(span);
            });
        }

        // Recommendations
        const recsList = document.getElementById('match-recs-list');
        recsList.innerHTML = '';
        const recs = data.recommendations || [];
        if (recs.length === 0) {
            recsList.innerHTML = '<li>No changes recommended. Ready to apply!</li>';
        } else {
            recs.forEach(rec => {
                const li = document.createElement('li');
                li.textContent = rec;
                recsList.appendChild(li);
            });
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const resumeId = resumeSelect.value;
        const jobDesc = jobDescInput.value.trim();
        if (!resumeId || !jobDesc) return;

        btnRunMatch.disabled = true;
        btnRunMatch.querySelector('span').textContent = 'Matching...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/jobmatch/match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ resume_id: resumeId, job_description: jobDesc })
            });

            if (!res.ok) throw new Error("Failed to match resume details.");
            const data = await res.json();
            displayMatchDetails(data);
        } catch (err) {
            alert(err.message);
        } finally {
            btnRunMatch.disabled = false;
            btnRunMatch.querySelector('span').textContent = 'Run Job Match Analysis';
        }
    });

    populateDropdown();
});