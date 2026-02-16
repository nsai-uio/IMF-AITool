document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const uploadStatus = document.getElementById('upload-status');
    const fileInput = document.getElementById('file-input');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatWindow = document.getElementById('chat-window');
    const chatSendButton = chatForm.querySelector('button');
    const selfCheckBtn = document.getElementById('self-check-btn');
    const selfCheckStatus = document.getElementById('self-check-status');

    let currentPdfFilename = null;
    let currentProcessedFilename = null;

    const pollTaskStatus = (taskId, onComplete, statusElement) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${taskId}`);
                const result = await response.json();

                if (result.status === 'processing') {
                    statusElement.textContent = `Processing: ${result.message} (${result.progress}%)`;
                    statusElement.style.color = 'orange';
                } else if (result.status === 'completed') {
                    clearInterval(interval);
                    statusElement.textContent = result.message;
                    statusElement.style.color = 'green';
                    onComplete(result);
                } else if (result.status === 'error') {
                    clearInterval(interval);
                    statusElement.textContent = `Error: ${result.message}`;
                    statusElement.style.color = 'red';
                } else if (result.status === 'not_found') {
                    // Task not registered yet, wait for next poll
                }
            } catch (error) {
                clearInterval(interval);
                statusElement.textContent = 'Error polling for status.';
                statusElement.style.color = 'red';
            }
        }, 2000);
    };

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData();
        if (fileInput.files.length === 0) {
            uploadStatus.textContent = 'Please select a file to upload.';
            uploadStatus.style.color = 'red';
            return;
        }
        formData.append('file', fileInput.files[0]);
        currentPdfFilename = fileInput.files[0].name;

        // Reset and disable UI elements
        chatInput.disabled = true;
        chatSendButton.disabled = true;
        selfCheckBtn.disabled = true;
        currentProcessedFilename = null;
        selfCheckStatus.textContent = '';

        uploadStatus.textContent = 'Uploading...';
        uploadStatus.style.color = 'orange';

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();

            if (response.ok) {
                pollTaskStatus(result.task_id, (completedResult) => {
                    currentProcessedFilename = completedResult.processed_file;
                    chatInput.disabled = false;
                    chatSendButton.disabled = false;
                    selfCheckBtn.disabled = false;
                    addMessageToChat('bot', `Ready! You can now ask questions about ${currentPdfFilename}.`);
                }, uploadStatus);
            } else {
                uploadStatus.textContent = `Error: ${result.error}`;
                uploadStatus.style.color = 'red';
                currentPdfFilename = null;
            }
        } catch (error) {
            uploadStatus.textContent = 'An unexpected error occurred during upload.';
            uploadStatus.style.color = 'red';
            currentPdfFilename = null;
        }
    });

    selfCheckBtn.addEventListener('click', async () => {
        if (!currentProcessedFilename) {
            selfCheckStatus.textContent = 'Please process a file first.';
            selfCheckStatus.style.color = 'red';
            return;
        }

        selfCheckStatus.textContent = 'Starting self-check...';
        selfCheckStatus.style.color = 'orange';

        try {
            const response = await fetch('/self_check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: currentProcessedFilename }),
            });
            const result = await response.json();
            if (response.ok) {
                pollTaskStatus(result.task_id, () => {}, selfCheckStatus);
            } else {
                selfCheckStatus.textContent = `Error: ${result.error}`;
                selfCheckStatus.style.color = 'red';
            }
        } catch (error) {
            selfCheckStatus.textContent = 'An unexpected error occurred during self-check.';
            selfCheckStatus.style.color = 'red';
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question || !currentPdfFilename) return;

        addMessageToChat('user', question);
        chatInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question, filename: currentPdfFilename }),
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