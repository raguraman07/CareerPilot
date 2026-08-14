import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const btnRunRoadmap = document.getElementById('btn-run-roadmap');
    const form = document.getElementById('roadmap-generator-form');
    const resultsWrapper = document.getElementById('roadmap-results-wrapper');
    const goalInput = document.getElementById('goal-input');
    const levelSelect = document.getElementById('level-select');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No user is logged in.");
        return session.access_token;
    };

    const displayRoadmap = (roadmapData) => {
        resultsWrapper.style.display = 'flex';
        resultsWrapper.innerHTML = '';

        const milestones = roadmapData.milestones || [];
        if (milestones.length === 0) {
            resultsWrapper.innerHTML = '<p style="color:var(--text-muted); padding-left:1rem;">No milestones generated.</p>';
            return;
        }

        milestones.forEach(m => {
            const item = document.createElement('div');
            item.className = 'milestone-item';
            
            const topicsHTML = (m.topics || []).map(t => `<span class="topic-tag">${t}</span>`).join('');

            item.innerHTML = `
                <div class="milestone-dot"></div>
                <div class="milestone-card">
                    <div class="milestone-phase">
                        <span>${m.phase}</span>
                        <span class="milestone-duration">${m.duration || 'Flexible'}</span>
                    </div>
                    <p class="milestone-desc">${m.description}</p>
                    <div class="milestone-topics">
                        ${topicsHTML}
                    </div>
                </div>
            `;
            resultsWrapper.appendChild(item);
        });
    };

    const loadLatestRoadmap = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/roadmap/latest`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data && data.roadmap_json) {
                    displayRoadmap(data.roadmap_json);
                    goalInput.value = data.goal || "";
                    levelSelect.value = data.current_level || "Entry-Level";
                }
            }
        } catch (e) {
            // Ignore error
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const goal = goalInput.value.trim();
        const level = levelSelect.value;
        if (!goal) return;

        btnRunRoadmap.disabled = true;
        btnRunRoadmap.querySelector('span').textContent = 'Generating...';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/roadmap/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ goal, current_level: level })
            });

            if (!res.ok) throw new Error("Failed to generate career roadmap.");
            const data = await res.json();
            displayRoadmap(data.roadmap_json);
        } catch (err) {
            alert(err.message);
        } finally {
            btnRunRoadmap.disabled = false;
            btnRunRoadmap.querySelector('span').textContent = 'Generate Roadmap';
        }
    });

    btnRunRoadmap.disabled = false;
    loadLatestRoadmap();
});