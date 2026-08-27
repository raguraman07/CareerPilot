import { supabase } from './supabaseClient.js';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:5000' 
    : 'https://careerpilot-txa0.onrender.com';

document.addEventListener('DOMContentLoaded', () => {
    const chatMessagesContainer = document.getElementById('chat-messages-container') || document.getElementById('chat-messages');
    const chatInputForm = document.getElementById('chat-form') || document.getElementById('chat-input-form');
    const chatUserInput = document.getElementById('chat-input') || document.getElementById('chat-user-input');
    const btnSendMsg = document.getElementById('btn-send-message') || document.getElementById('btn-send-msg');
    const statusMsg = document.getElementById('chat-status-msg');
    const btnNewChat = document.getElementById('btn-new-chat');
    const currentChatTitle = document.getElementById('current-chat-title');
    const chatsHistoryList = document.getElementById('chat-history-list') || document.getElementById('chats-history-list');

    let activeChatId = null;

    const getAuthToken = async () => {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (error || !session) return null;
        return session.access_token;
    };

    const formatMarkdown = (text) => {
        if (!text) return '';
        let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        
        // Code blocks
        escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre class="chat-code-block"><code>$1</code></pre>');
        // Inline code
        escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Headers
        escaped = escaped.replace(/^### (.*$)/gim, '<h5 class="chat-h3">$1</h5>');
        escaped = escaped.replace(/^## (.*$)/gim, '<h4 class="chat-h2">$1</h4>');
        escaped = escaped.replace(/^# (.*$)/gim, '<h3 class="chat-h1">$1</h3>');
        
        // Bold & Italic
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Unordered lists (- or *)
        escaped = escaped.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="chat-list-item">$1</li>');
        escaped = escaped.replace(/(<li class="chat-list-item">.*<\/li>\s*)+/gim, '<ul class="chat-ul">$&</ul>');
        
        // Numbered lists (1., 2., etc.)
        escaped = escaped.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="chat-num-item"><span class="chat-num">$1.</span> $2</li>');
        escaped = escaped.replace(/(<li class="chat-num-item">.*<\/li>\s*)+/gim, '<ol class="chat-ol">$&</ol>');
        
        // Double newlines to paragraph spacers, single to linebreaks
        escaped = escaped.replace(/\n\n+/g, '<div class="chat-spacer"></div>');
        escaped = escaped.replace(/\n/g, '<br>');
        
        return escaped;
    };

    const appendMessage = (role, content, sourcesUsed = []) => {
        if (!chatMessagesContainer) return;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${role === 'user' ? 'user' : 'assistant'}`;
        
        let htmlContent = formatMarkdown(content);
        if (role === 'assistant' && sourcesUsed && sourcesUsed.length > 0) {
            const sourcesStr = sourcesUsed.join(', ');
            htmlContent += `<br><span class="sources-tag" style="font-size:0.8rem; color:var(--text-muted);">📄 Context: ${sourcesStr}</span>`;
        }
        
        bubble.innerHTML = htmlContent;
        chatMessagesContainer.appendChild(bubble);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    };

    const startNewChat = () => {
        activeChatId = null;
        if (currentChatTitle) currentChatTitle.textContent = "New Conversation";
        if (chatUserInput) chatUserInput.value = '';
        
        if (chatMessagesContainer) {
            chatMessagesContainer.innerHTML = `
                <div class="chat-bubble assistant">
                    Hello! I'm your AI Career Coach. How can I help you optimize your resume, prepare for target roles, or close your skill gaps today?
                </div>
            `;
        }
    };

    const loadChatHistory = async () => {
        if (!chatsHistoryList) return;
        try {
            const token = await getAuthToken();
            if (!token) return;

            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chats`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error();
            const chats = await res.json();

            chatsHistoryList.innerHTML = '';
            if (!Array.isArray(chats) || chats.length === 0) {
                chatsHistoryList.innerHTML = '<p style="font-size:0.85rem; color:var(--text-muted); padding:0.5rem;">No saved conversations.</p>';
                return;
            }

            chats.forEach(chat => {
                const item = document.createElement('div');
                item.className = 'history-item';
                item.style.padding = '0.5rem';
                item.style.cursor = 'pointer';
                item.style.borderRadius = 'var(--radius-sm)';
                item.innerHTML = `<span style="font-size:0.85rem; font-weight:500;">${chat.title || 'Conversation'}</span>`;
                
                item.addEventListener('click', async () => {
                    activeChatId = chat.id;
                    if (currentChatTitle) currentChatTitle.textContent = chat.title || 'Conversation';
                    
                    try {
                        const chatRes = await fetch(`${API_BASE_URL}/api/career-assistant/chat/${chat.id}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (chatRes.ok) {
                            const chatData = await chatRes.json();
                            if (chatMessagesContainer) {
                                chatMessagesContainer.innerHTML = '';
                                (chatData.messages || []).forEach(m => {
                                    appendMessage(m.role, m.content, m.sources_used || []);
                                });
                            }
                        }
                    } catch (e) {
                        console.error("Failed to load conversation details:", e);
                    }
                });

                chatsHistoryList.appendChild(item);
            });

        } catch (e) {
            console.error("Chat history load error:", e);
        }
    };

    const sendMessage = async () => {
        const message = chatUserInput ? chatUserInput.value.trim() : '';
        if (!message) return;

        appendMessage('user', message);
        if (chatUserInput) chatUserInput.value = '';

        if (btnSendMsg) btnSendMsg.disabled = true;
        if (statusMsg) {
            statusMsg.style.display = 'inline';
            statusMsg.textContent = 'AI Coach is thinking...';
        }

        try {
            const token = await getAuthToken();
            if (!token) throw new Error("Please log in to chat.");

            const res = await fetch(`${API_BASE_URL}/api/career-assistant/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    chat_id: activeChatId,
                    message: message
                })
            });

            const data = await res.json();

            if (!res.ok || data.success === false) {
                throw new Error(data.error || "Failed to receive response from AI Coach.");
            }

            if (data.chat_id) activeChatId = data.chat_id;

            if (statusMsg) statusMsg.style.display = 'none';
            appendMessage('assistant', data.response, data.sources_used || []);
            loadChatHistory();

        } catch (err) {
            if (statusMsg) statusMsg.style.display = 'none';
            appendMessage('assistant', `Sorry, I encountered an error: ${err.message || "Unable to send message."}`);
        } finally {
            if (btnSendMsg) btnSendMsg.disabled = false;
        }
    };

    if (chatInputForm) {
        chatInputForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendMessage();
        });
    }

    if (btnSendMsg) {
        btnSendMsg.addEventListener('click', (e) => {
            sendMessage();
        });
    }

    if (btnNewChat) {
        btnNewChat.addEventListener('click', () => {
            startNewChat();
        });
    }

    const init = async () => {
        const token = await getAuthToken();
        if (token) {
            loadChatHistory();
        }

        supabase.auth.onAuthStateChange((event, session) => {
            if (session) {
                loadChatHistory();
            }
        });
    };

    init();
});