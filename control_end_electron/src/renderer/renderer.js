// 主入口 - 只负责启动应用
import App from './js/app.js';
import Logger from './js/utils/logger.js';

document.addEventListener('DOMContentLoaded', async () => {
    try {
        Logger.info('Initializing WOZ Training System...');
        
        // 初始化应用
        const app = new App();
        await app.initialize();
        
        Logger.info('Application initialized successfully');
    } catch (error) {
        Logger.error('Failed to initialize application:', error);
        document.body.innerHTML = `
            <div class="error-container">
                <h2>应用启动失败</h2>
                <p>错误信息: ${error.message}</p>
                <button onclick="location.reload()">重新加载</button>
            </div>
        `;
    }
});