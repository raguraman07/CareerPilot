import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const resumeSelect = document.getElementById('resume-select');
    const btnRunInterview = document.getElementById('btn-run-interview');
    const form = document.getElementById('interview-generator-form');
    const resultsWrapper = document.getElementById('interview-results-wrapper');
    const difficultySelect = document.getElementById('difficulty-select');
    const categorySelect = document.getElementById('category-select');

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
            btnRunInterview.disabled = false;
        } catch (err) {
            resumeSelect.innerHTML = '<option value="" disabled>Error loading resumes.</option>';
        }
    };

    const displayQuestions = (questions) => {
        resultsWrapper.style.display = 'flex';
        resultsWrapper.innerHTML = '';

        if (!questions || questions.length === 0) {
            resultsWrapper.innerHTML = '<p style="color:var(--text-muted);">No questions generated.</p>';
            return;
        }

        questions.forEach((q, index) => {
            const card = document.createElement('div');
            card.className = 'question-card';
            card.innerHTML = `
                <div class="q-header">
                    <span class="q-number">Question ${index + 1}</span>
                    <button class="btn-toggle-hint" data-index="${index}">Toggle Hint</button>
                </div>
                <div class="q-text">${q.question}</div>
                <div class="hint-box" id="hint-${index}">${q.hint || 'Try answering contextually based on your skills.'}</div>
                <div class="form-group">
                    <label class="form-label">Draft Your Practice Answer</label>
                    <textarea class="user-answer-textarea" placeholder="Type your response to practice drafting details..."></textarea>
                </div>
                <div class="guideline-box">
                    <strong>Answer Guidelines:</strong> ${q.answer_guideline || 'Ensure you mention details using the STAR framework.'}
                </div>
            `;
            resultsWrapper.appendChild(card);
        });

        // Add hint button listeners
        resultsWrapper.querySelectorAll('.btn-toggle-hint').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = btn.getAttribute('data-index');
                const hintEl = document.getElementById(`hint-${idx}`);
                if (hintEl) {
                    const isVisible = hintEl.style.display === 'block';
                    hintEl.style.display = isVisible ? 'none' : 'block';
                }
            });
        });
    };

    const loadLatestInterview = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/interview/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.length > 0) {
                    displayQuestions(data[0].questions);
                }
            }
        } catch (e) {
            // Ignore error
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const resumeId = resumeSelect.value;
        const difficulty = difficultySelect.value;
        const category = categorySelect.value;
        if (!resumeId) return;

        btnRunInterview.disabled = true;
        btnRunInterview.querySelector('span').textContent = 'Generating...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/interview/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ resume_id: resumeId, difficulty, category })
            });

            if (!res.ok) throw new Error("Failed to generate questions.");
            const data = await res.json();
            displayQuestions(data.questions);
        } catch (err) {
            alert(err.message);
        } finally {
            btnRunInterview.disabled = false;
            btnRunInterview.querySelector('span').textContent = 'Generate Questions';
        }
    });

    populateDropdown().then(loadLatestInterview);
});