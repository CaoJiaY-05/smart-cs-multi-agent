document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chatWindow');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const historyList = document.getElementById('historyList');

    // 绑定发送事件
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // 发送消息
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // 1. 添加用户消息
        addMessage('user', message);
        userInput.value = '';

        // 2. 添加加载提示
        const loadingId = addLoadingMessage();

        try {
            // 3. 调用后端接口
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: "test_001",
                    message: message
                })
            });

            const data = await response.json();
            
            // 4. 移除加载提示，添加机器人回复
            removeLoadingMessage(loadingId);
            addMessage('robot', data.response);

            // 5. 添加到历史记录
            addToHistory(message);

        } catch (error) {
            removeLoadingMessage(loadingId);
            addMessage('robot', '服务连接失败，请检查后端是否启动');
        }
    }

    // 添加消息
    function addMessage(type, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        const bubble = document.createElement('div');
        bubble.className = 'message-content';
        bubble.textContent = text;

        messageDiv.appendChild(bubble);
        chatWindow.appendChild(messageDiv);

        // 自动滚动到底部
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // 添加加载中消息
    function addLoadingMessage() {
        const id = Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message robot';
        messageDiv.id = `loading-${id}`;

        const bubble = document.createElement('div');
        bubble.className = 'message-content';
        bubble.textContent = '正在处理您的请求...';

        messageDiv.appendChild(bubble);
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        return id;
    }

    // 移除加载中消息
    function removeLoadingMessage(id) {
        const loadingMsg = document.getElementById(`loading-${id}`);
        if (loadingMsg) loadingMsg.remove();
    }

    // 填充输入框
    function fillInput(text) {
        userInput.value = text;
        userInput.focus();
    }

    // 添加到历史记录
    function addToHistory(text) {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = '#';
        a.textContent = text.substring(0, 10) + (text.length > 10 ? '...' : '');
        a.onclick = () => fillInput(text);
        li.appendChild(a);
        historyList.appendChild(li);
    }

    // 把fillInput暴露到全局，方便HTML调用
    window.fillInput = fillInput;
});