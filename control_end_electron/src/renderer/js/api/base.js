// API基础类 - 提供统一的HTTP请求接口
import Logger from '../utils/logger.js';
import { Helpers } from '../utils/helpers.js';
import CONFIG from '../config.js';

export class APIError extends Error {
    constructor(message, status, response) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.response = response;
    }
}

export class BaseAPI {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
        this.timeout = 10000; // 10秒超时
    }

    // HTTP GET请求
    async get(endpoint, options = {}) {
        return this.request('GET', endpoint, null, options);
    }

    // HTTP POST请求
    async post(endpoint, data = null, options = {}) {
        return this.request('POST', endpoint, data, options);
    }

    // HTTP PUT请求
    async put(endpoint, data = null, options = {}) {
        return this.request('PUT', endpoint, data, options);
    }

    // HTTP DELETE请求
    async delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, null, options);
    }

    // 上传文件
    async upload(endpoint, formData, options = {}) {
        const uploadOptions = {
            ...options,
            headers: {
                ...options.headers
                // 不设置Content-Type，让浏览器自动设置multipart/form-data
            }
        };
        
        return this.request('POST', endpoint, formData, uploadOptions);
    }

    // 通用请求方法
    async request(method, endpoint, data = null, options = {}) {
        const url = this.buildURL(endpoint);
        const config = this.buildRequestConfig(method, data, options);

        try {
            Logger.debug(`${method} ${url}`, { data, options });
            
            const response = await this.fetchWithTimeout(url, config);
            const result = await this.handleResponse(response);
            
            Logger.debug(`${method} ${url} - Success`, result);
            return result;
            
        } catch (error) {
            Logger.error(`${method} ${url} - Error`, error);
            throw error;
        }
    }

    buildURL(endpoint) {
        const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
        const cleanBaseURL = this.baseURL.endsWith('/') ? this.baseURL.slice(0, -1) : this.baseURL;
        return cleanBaseURL ? `${cleanBaseURL}/${cleanEndpoint}` : cleanEndpoint;
    }

    buildRequestConfig(method, data, options) {
        const config = {
            method,
            headers: {
                ...this.defaultHeaders,
                ...options.headers
            },
            ...options
        };

        // 处理请求体
        if (data !== null) {
            if (data instanceof FormData) {
                config.body = data;
                // 删除Content-Type让浏览器自动设置
                delete config.headers['Content-Type'];
            } else if (typeof data === 'object') {
                config.body = JSON.stringify(data);
            } else {
                config.body = data;
            }
        }

        return config;
    }

    async fetchWithTimeout(url, config) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new APIError('Request timeout', 408, null);
            }
            throw error;
        }
    }

    async handleResponse(response) {
        // 检查响应状态
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            let errorData = null;

            try {
                errorData = await response.json();
                if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (e) {
                // 如果无法解析JSON，使用默认错误消息
                try {
                    errorMessage = await response.text() || errorMessage;
                } catch (e2) {
                    // 如果连文本都无法读取，使用默认消息
                }
            }

            throw new APIError(errorMessage, response.status, errorData);
        }

        // 解析响应
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else if (response.status === 204) {
            return null; // No Content
        } else {
            return await response.text();
        }
    }

    // 设置认证头
    setAuthToken(token) {
        this.defaultHeaders['Authorization'] = `Bearer ${token}`;
    }

    // 移除认证头
    clearAuth() {
        delete this.defaultHeaders['Authorization'];
    }

    // 设置超时时间
    setTimeout(ms) {
        this.timeout = ms;
    }
}

// 创建默认实例，配置后端API地址
const apiInstance = new BaseAPI(CONFIG.API.BASE_URL);
apiInstance.setTimeout(CONFIG.API.TIMEOUT);
export default apiInstance;
