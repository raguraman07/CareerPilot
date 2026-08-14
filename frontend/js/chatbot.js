import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:5000' : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const form = document.getElementById('chat-form');
    const btnSend = document.getElementById('btn-send-msg');

    const getAuthToken = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("No user is logged in.");
        return session.access_token;
    };

    const appendBubble = (message, sender) => {
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${sender}`;
        bubble.textContent = message;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const showTypingIndicator = () => {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        chatMessages.appendChild(indicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const removeTypingIndicator = () => {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    };

    const loadHistory = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/chat/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.length > 0) {
                    // Clear initial greetings if we have history
                    chatMessages.innerHTML = '';
                    data.forEach(msg => {
                        appendBubble(msg.message, msg.sender);
                    });
                }
            }
        } catch (e) {
            // Ignore error
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;

        chatInput.value = '';
        appendBubble(msg, 'user');
        showTypingIndicator();
        chatInput.disabled = true;
        btnSend.disabled = true;

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/chat/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ message: msg })
            });

            if (!res.ok) throw new Error("Failed to send chat message.");
            const data = await res.json();
            removeTypingIndicator();
            appendBubble(data.reply, 'bot');
        } catch (err) {
            removeTypingIndicator();
            appendBubble("Error connecting to AI Coach. Please try again later.", 'bot');
        } finally {
            chatInput.disabled = false;
            btnSend.disabled = false;
            chatInput.focus();
        }
    });

    loadHistory();
});