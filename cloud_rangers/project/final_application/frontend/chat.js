// AI Chat JavaScript — Uses ONLY live API, no simulated responses

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const typingIndicator = document.getElementById('typingIndicator');
    const sendBtn = document.getElementById('sendBtn');

    // Auto-resize textarea
    if (chatInput) {
        chatInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            if (sendBtn) sendBtn.disabled = this.value.trim() === '';
        });
        if (sendBtn) sendBtn.disabled = true;
    }

    // Handle form submission
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }

    // Handle Enter key (Shift+Enter for new line)
    if (chatInput) {
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (this.value.trim() !== '') {
                    sendMessage();
                }
            }
        });
    }
});

// Send message function — always uses real API
async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) sendBtn.disabled = true;

    // Show typing indicator
    showTypingIndicator();

    try {
        // Get product context from localStorage
        const productDataRaw = localStorage.getItem('currentProductData');
        let context = null;
        if (productDataRaw) {
            try { context = JSON.parse(productDataRaw); } catch (e) { }
        }

        // Get health profile for personalized responses
        const profileRaw = localStorage.getItem('healthProfile');
        let profile = null;
        if (profileRaw) {
            try { profile = JSON.parse(profileRaw); } catch (e) { }
        }

        // Enrich context with profile
        if (context && profile) {
            context.user_profile = profile;
        }

        const API_URL = 'http://localhost:5000/api';
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                context: context
            })
        });

        if (!response.ok) throw new Error('API Error');
        const data = await response.json();

        hideTypingIndicator();

        if (data.error) {
            addMessage("⚠️ " + data.error, 'ai');
        } else {
            addMessage(data.response, 'ai');
        }

    } catch (error) {
        console.error('Chat error:', error);
        hideTypingIndicator();
        addMessage(
            "⚠️ I'm having trouble connecting to the AI service. " +
            "Please make sure the backend is running (`python api.py` on port 5000). " +
            "Your product analysis on the dashboard is still fully functional with OpenFoodFacts data.",
            'ai'
        );
    }
}

// Add message to chat
function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messageWrapper = document.createElement('div');
    messageWrapper.className = `message-wrapper ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = type === 'ai' ? '<i class="bi bi-robot"></i>' : '<i class="bi bi-person-fill"></i>';

    const content = document.createElement('div');
    content.className = 'message-content';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Convert line breaks to <br> and format text
    const formattedText = formatMessageText(text);
    bubble.innerHTML = formattedText;

    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = 'Just now';

    content.appendChild(bubble);
    content.appendChild(time);

    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(content);

    chatMessages.appendChild(messageWrapper);

    // Scroll to bottom
    scrollToBottom();
}

// Format message text
function formatMessageText(text) {
    // Convert URLs to links
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    text = text.replace(urlRegex, '<a href="$1" target="_blank">$1</a>');

    // Bold: **text**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Bullet points: • or * at start of line
    text = text.replace(/^[•*]\s(.*)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Convert remaining line breaks to <br>
    text = text.replace(/\n(?!<li>)/g, '<br>');

    return text;
}

// Show typing indicator
function showTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.style.display = 'block';
        scrollToBottom();
    }
}

// Hide typing indicator
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.style.display = 'none';
    }
}

// Scroll chat to bottom
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }
}

// Quick message function
function sendQuickMessage(message) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = message;
        chatInput.dispatchEvent(new Event('input'));
        sendMessage();
    }
}