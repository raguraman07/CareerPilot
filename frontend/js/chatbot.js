import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : `http://${window.location.hostname}:5000`;

document.addEventListener('DOMContentLoaded', () => {
    const chatMessagesContainer = document.getElementById('chat-messages');
    const chatInputForm = document.getElementById('chat-input-form');
    const chatUserInput = document.getElementById('chat-user-input');
    const btnSendMsg = document.getElementById('btn-send-msg');
    const chatStatusMsg = document.getElementById('chat-status-msg');
    const btnNewChat = document.getElementById('btn-new-chat');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const btnDeleteChat = document.getElementById('btn-delete-chat');
    const currentChatTitle = document.getElementById('current-chat-title');
    const chatsHistoryList = document.getElementById('chats-history-list');

    let activeChatId = null;

    const getAuthToken = async () => {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (error || !session) throw new Error("Authentication required. Please log in.");
        return session.access_token;
    };

    // Format simple text formatting (bold, newlines, code) into basic HTML
    const formatMarkdown = (text) => {
        if (!text) return '';
        let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
        escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
        escaped = escaped.replace(/\n/g, '<br>');
        return escaped;
    };

    // Append Message to Thread
    const appendMessage = (role, content, sourcesUsed = []) => {
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${role === 'user' ? 'user' : 'assistant'}`;
        
        let htmlContent = formatMarkdown(content);
        if (role === 'assistant' && sourcesUsed && sourcesUsed.length > 0) {
            const sourcesStr = sourcesUsed.join(', ');
            htmlContent += `<br><span class="sources-tag">📄 Context: ${sourcesStr}</span>`;
        }
        
        bubble.innerHTML = htmlContent;
        chatMessagesContainer.appendChild(bubble);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    };

    // Render Full Chat Session
    const renderChatSession = (chatData) => {
        activeChatId = chatData.id;
        currentChatTitle.textContent = chatData.title || "Conversation";

        // Keep starter pills and welcome message, clear past messages
        const pillsBlock = chatMessagesContainer.querySelector('.starter-pills')?.parentElement;
        const welcomeBlock = chatMessagesContainer.querySelector('.message-bubble.assistant');
        
        chatMessagesContainer.innerHTML = '';
        if (welcomeBlock) chatMessagesContainer.appendChild(welcomeBlock);
        if (pillsBlock) chatMessagesContainer.appendChild(pillsBlock);

        const messages = chatData.messages || [];
        messages.forEach(m => {
            appendMessage(m.role, m.content, m.sources_used || []);
        });
    };

    // Reset to New Conversation View
    const startNewChat = () => {
        activeChatId = null;
        currentChatTitle.textContent = "New Conversation";
        chatUserInput.value = '';
        
        const pillsBlock = chatMessagesContainer.querySelector('.starter-pills')?.parentElement;
        const welcomeBlock = chatMessagesContainer.querySelector('.message-bubble.assistant');
        
        chatMessagesContainer.innerHTML = '';
        if (welcomeBlock) chatMessagesContainer.appendChild(welcomeBlock);
        if (pillsBlock) chatMessagesContainer.appendChild(pillsBlock);
    };

    // 1. Fetch & Render Conversation History Sidebar
    const loadChatHistory = async () => {
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chats`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const chats = await res.json();

            chatsHistoryList.innerHTML = '';
            if (!Array.isArray(chats) || chats.length === 0) {
                chatsHistoryList.innerHTML = '<p style="font-size:0.85rem; color:var(--text-muted);">No saved conversations.</p>';
                return;
            }

            chats.forEach(c => {
                const btn = document.createElement('button');
                btn.className = `btn btn-secondary ${c.id === activeChatId ? 'active-chat-btn' : ''}`;
                btn.style.width = '100%';
                btn.style.justify = 'flex-start';
                btn.style.fontSize = '0.85rem';
                btn.style.padding = '0.45rem 0.75rem';
                btn.style.overflow = 'hidden';
                btn.style.textOverflow = 'ellipsis';
                btn.style.whiteSpace = 'nowrap';
                btn.textContent = c.title || 'Conversation';
                btn.setAttribute('data-id', c.id);

                btn.addEventListener('click', async () => {
                    try {
                        const t = await getAuthToken();
                        const r = await fetch(`${API_BASE_URL}/api/career-assistant/chats/${c.id}`, {
                            headers: { 'Authorization': `Bearer ${t}` }
                        });
                        if (r.ok) {
                            const chatObj = await r.json();
                            renderChatSession(chatObj);
                        }
                    } catch (err) {
                        console.error("Error loading chat:", err);
                    }
                });

                chatsHistoryList.appendChild(btn);
            });
        } catch (err) {
            console.error("Error loading chats sidebar:", err);
            chatsHistoryList.innerHTML = '<p style="font-size:0.85rem; color:var(--text-muted);">Unable to load history.</p>';
        }
    };

    // 2. Submit Chat Message
    const sendMessage = async (messageText) => {
        if (!messageText.trim()) return;

        appendMessage('user', messageText);
        chatUserInput.value = '';

        btnSendMsg.disabled = true;
        btnSendMsg.querySelector('span').textContent = 'Thinking...';
        chatStatusMsg.style.display = 'block';

        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    chat_id: activeChatId || undefined,
                    message: messageText
                })
            });

            const data = await res.json();
            if (!res.ok) {
                appendMessage('assistant', data.error || "AI Career Assistant is temporarily unavailable. Please try again.");
                return;
            }

            activeChatId = data.chat_id;
            currentChatTitle.textContent = messageText.length > 35 ? messageText.substring(0, 35) + '...' : messageText;
            appendMessage('assistant', data.reply, data.sources_used || []);
            loadChatHistory();

        } catch (err) {
            console.error("Chat send error:", err);
            appendMessage('assistant', "AI Career Assistant is temporarily unavailable. Please try again.");
        } finally {
            btnSendMsg.disabled = false;
            btnSendMsg.querySelector('span').textContent = 'Send';
            chatStatusMsg.style.display = 'none';
        }
    };

    // Form Submit Event
    chatInputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage(chatUserInput.value.trim());
    });

    // Starter Question Pills Click Event
    document.querySelectorAll('.pill-btn').forEach(pill => {
        pill.addEventListener('click', () => {
            const q = pill.getAttribute('data-q');
            if (q) sendMessage(q);
        });
    });

    // New Chat Button
    btnNewChat.addEventListener('click', startNewChat);

    // Clear Chat Button
    btnClearChat.addEventListener('click', async () => {
        if (!activeChatId) {
            startNewChat();
            return;
        }
        if (!confirm("Clear message history for this conversation?")) return;
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chats/${activeChatId}/clear`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                startNewChat();
            }
        } catch (err) {
            console.error("Clear chat error:", err);
        }
    });

    // Delete Chat Button
    btnDeleteChat.addEventListener('click', async () => {
        if (!activeChatId) return;
        if (!confirm("Delete this conversation completely?")) return;
        try {
            const token = await getAuthToken();
            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chats/${activeChatId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                startNewChat();
                loadChatHistory();
            }
        } catch (err) {
            console.error("Delete chat error:", err);
        }
    });

    // Initial load
    loadChatHistory();
});