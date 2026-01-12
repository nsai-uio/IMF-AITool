document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const uploadStatus = document.getElementById('upload-status');
    const fileInput = document.getElementById('file-input');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatWindow = document.getElementById('chat-window');
    const chatSendButton = chatForm.querySelector('button');

    let currentFilename = null;

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData();
        if (fileInput.files.length === 0) {
            uploadStatus.textContent = 'Please select a file to upload.';
            uploadStatus.style.color = 'red';
            return;
        }
        formData.append('file', fileInput.files[0]);
        currentFilename = fileInput.files[0].name;

        uploadStatus.textContent = 'Uploading and processing...';
        uploadStatus.style.color = 'orange';

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (response.ok) {
                uploadStatus.textContent = result.message;
                uploadStatus.style.color = 'green';
                chatInput.disabled = false;
                chatSendButton.disabled = false;
                addMessageToChat('bot', `Ready! You can now ask questions about ${currentFilename}.`);
            } else {
                uploadStatus.textContent = `Error: ${result.error}`;
                uploadStatus.style.color = 'red';
                currentFilename = null;
            }
        } catch (error) {
            uploadStatus.textContent = 'An unexpected error occurred.';
            uploadStatus.style.color = 'red';
            currentFilename = null;
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question || !currentFilename) return;

        addMessageToChat('user', question);
        chatInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question, filename: currentFilename }),
            });

            const result = await response.json();

            if (response.ok) {
                addMessageToChat('bot', result.answer);
            } else {
                addMessageToChat('bot', `Error: ${result.error}`);
            }
        } catch (error) {
            addMessageToChat('bot', 'An unexpected error occurred while fetching the answer.');
        }
    });

    function addMessageToChat(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', sender);
        const p = document.createElement('p');
        p.textContent = message;
        messageElement.appendChild(p);
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
});