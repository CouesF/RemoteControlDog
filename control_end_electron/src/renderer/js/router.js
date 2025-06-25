// 路由管理器 - 负责页面导航和状态管理
import EventBus from './eventBus.js';
import Logger from './utils/logger.js';
import { EVENTS, PAGES } from './utils/constants.js';

// 懒加载页面组件
const pageModules = {
    [PAGES.PARTICIPANT_MANAGEMENT]: () => import('./pages/ParticipantManagement.js'),
    [PAGES.MAP_MANAGEMENT]: () => import('./pages/MapManagement.js'),
    [PAGES.EXPERIMENT_CONTROL]: () => import('./pages/ExperimentControl.js'),
    [PAGES.SESSION_RESULTS]: () => import('./pages/SessionResults.js')
};

export default class Router {
    constructor() {
        this.contentArea = null;
        this.currentPage = null;
        this.navigationHistory = [];
        this.navLinks = null;
    }

    async initialize() {
        this.contentArea = document.getElementById('content-area');
        if (!this.contentArea) {
            throw new Error('Content area not found');
        }

        this.setupNavigation();
        this.setupEventListeners();
        Logger.info('Router initialized');
    }

    setupNavigation() {
        this.navLinks = document.querySelectorAll('.nav-menu a');
        this.navLinks.forEach(link => {
            link.addEventListener('click', async (event) => {
                event.preventDefault();
                const page = link.getAttribute('data-page');
                await this.navigate(page, { triggeredBy: 'navigation' });
            });
        });
    }

    setupEventListeners() {
        // 监听全局导航事件
        EventBus.on(EVENTS.NAVIGATE_TO, async ({ page, options }) => {
            await this.navigate(page, options);
        });

        // 监听浏览器后退按钮
        window.addEventListener('popstate', async (event) => {
            if (event.state && event.state.page) {
                await this.navigate(event.state.page, { skipHistory: true });
            }
        });
    }

    async navigate(pageName, options = {}) {
        try {
            Logger.info(`Navigating to: ${pageName}`);

            // 验证页面名称
            if (!pageModules[pageName]) {
                throw new Error(`Page not found: ${pageName}`);
            }

            // 清理当前页面
            await this.cleanupCurrentPage();

            // 更新导航状态
            this.updateNavigationState(pageName);

            // 加载并渲染新页面
            const PageClass = await this.loadPage(pageName);
            this.currentPage = new PageClass.default();
            await this.currentPage.render(this.contentArea);

            // 更新历史记录
            if (!options.skipHistory) {
                this.updateHistory(pageName);
            }

            // 触发导航完成事件
            EventBus.emit(EVENTS.NAVIGATION_COMPLETE, { 
                page: pageName, 
                options 
            });

            Logger.info(`Navigation to ${pageName} completed`);

        } catch (error) {
            Logger.error(`Navigation to ${pageName} failed:`, error);
            await this.handleNavigationError(error, pageName);
        }
    }

    async loadPage(pageName) {
        try {
            const module = await pageModules[pageName]();
            return module;
        } catch (error) {
            Logger.error(`Failed to load page module: ${pageName}`, error);
            throw new Error(`Failed to load page: ${pageName}`);
        }
    }

    async cleanupCurrentPage() {
        if (this.currentPage) {
            try {
                if (typeof this.currentPage.cleanup === 'function') {
                    await this.currentPage.cleanup();
                }
            } catch (error) {
                Logger.error('Error during page cleanup:', error);
            }
            this.currentPage = null;
        }
    }

    updateNavigationState(pageName) {
        // 更新活动导航链接
        this.navLinks.forEach(link => {
            const linkPage = link.getAttribute('data-page');
            if (linkPage === pageName) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    updateHistory(pageName) {
        this.navigationHistory.push(pageName);
        
        // 限制历史记录长度
        if (this.navigationHistory.length > 50) {
            this.navigationHistory.shift();
        }

        // 更新浏览器历史
        const state = { page: pageName };
        window.history.pushState(state, '', `#${pageName}`);
    }

    async handleNavigationError(error, pageName) {
        Logger.error('Navigation error:', error);
        
        this.contentArea.innerHTML = `
            <div class="error-page">
                <h2>页面加载失败</h2>
                <p>无法加载页面: ${pageName}</p>
                <p>错误信息: ${error.message}</p>
                <div class="error-actions">
                    <button class="btn btn-primary" onclick="location.reload()">重新加载</button>
                    <button class="btn btn-secondary" onclick="history.back()">返回上页</button>
                </div>
            </div>
        `;
    }

    goBack() {
        if (this.navigationHistory.length > 1) {
            this.navigationHistory.pop(); // 移除当前页面
            const previousPage = this.navigationHistory[this.navigationHistory.length - 1];
            this.navigate(previousPage, { skipHistory: true });
        }
    }

    getCurrentPage() {
        return this.currentPage;
    }

    getNavigationHistory() {
        return [...this.navigationHistory];
    }
}