// 地图相关API
import { BaseAPI } from './base.js';
import { API_ENDPOINTS } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';
import CONFIG from '../config.js';

class MapsAPI extends BaseAPI {
    constructor() {
        // 使用WOZ系统后端地址
        super('http://118.31.58.101:48995/api');
        this.setTimeout(CONFIG.API.TIMEOUT);
        this.endpoint = '/maps';
    }

    // 获取所有地图
    async getAll() {
        try {
            return await this.get(this.endpoint);
        } catch (error) {
            Logger.error('Failed to get maps:', error);
            throw error;
        }
    }

    // 根据ID获取地图
    async getById(mapId) {
        try {
            return await this.get(`${this.endpoint}/${mapId}`);
        } catch (error) {
            Logger.error(`Failed to get map ${mapId}:`, error);
            throw error;
        }
    }

    // 创建新地图
    async create(mapData) {
        try {
            // 验证数据
            const errors = Validator.validateMap(mapData);
            if (errors.length > 0) {
                throw new Error(`Validation failed: ${errors.map(e => e.message).join(', ')}`);
            }

            return await this.post(this.endpoint, mapData);
        } catch (error) {
            Logger.error('Failed to create map:', error);
            throw error;
        }
    }

    // 更新地图
    async update(mapId, mapData) {
        try {
            // 验证数据
            const errors = Validator.validateMap(mapData);
            if (errors.length > 0) {
                throw new Error(`Validation failed: ${errors.map(e => e.message).join(', ')}`);
            }

            return await this.put(`${this.endpoint}/${mapId}`, mapData);
        } catch (error) {
            Logger.error(`Failed to update map ${mapId}:`, error);
            throw error;
        }
    }

    // 删除地图
    async delete(mapId) {
        try {
            // 直接调用父类的delete方法，它会处理好请求和响应
            await super.delete(`${this.endpoint}/${mapId}`);
            return true; // 明确返回true表示成功
        } catch (error) {
            Logger.error(`Failed to delete map ${mapId}:`, error);
            throw error;
        }
    }

    // 获取地图的目标点
    async getTargets(mapId) {
        try {
            return await this.get(`${this.endpoint}/${mapId}/targets`);
        } catch (error) {
            Logger.error(`Failed to get targets for map ${mapId}:`, error);
            throw error;
        }
    }

    // 为地图添加目标点
    async addTarget(mapId, targetData) {
        try {
            // 构建FormData用于文件上传
            const formData = new FormData();
            formData.append('targetName', targetData.targetName);
            formData.append('description', targetData.description || '');
            formData.append('pose', JSON.stringify(targetData.pose));
            
            if (targetData.targetImgFile) {
                formData.append('targetImgFile', targetData.targetImgFile);
            }
            if (targetData.envImgFile) {
                formData.append('envImgFile', targetData.envImgFile);
            }
            
            return await this.upload(`${this.endpoint}/${mapId}/targets`, formData);
        } catch (error) {
            Logger.error(`Failed to add target to map ${mapId}:`, error);
            throw error;
        }
    }

    // 更新目标点
    async updateTarget(targetId, targetData) {
        try {
            // 构建FormData用于文件上传
            const formData = new FormData();
            formData.append('targetName', targetData.targetName);
            formData.append('description', targetData.description || '');
            formData.append('pose', JSON.stringify(targetData.pose));
            
            if (targetData.targetImgFile) {
                formData.append('targetImgFile', targetData.targetImgFile);
            }
            if (targetData.envImgFile) {
                formData.append('envImgFile', targetData.envImgFile);
            }
            
            return await this.upload(`/targets/${targetId}`, formData, 'PUT');
        } catch (error) {
            Logger.error(`Failed to update target ${targetId}:`, error);
            throw error;
        }
    }

    // 删除目标点
    async deleteTarget(targetId) {
        try {
            await super.delete(`/targets/${targetId}`);
            return true;
        } catch (error) {
            Logger.error(`Failed to delete target ${targetId}:`, error);
            throw error;
        }
    }

    // 更新目标点顺序
    async updateTargetsOrder(mapId, targetIds) {
        try {
            const orderData = { targetIds };
            await this.put(`${this.endpoint}/${mapId}/targets/order`, orderData);
            return true;
        } catch (error) {
            Logger.error(`Failed to update targets order for map ${mapId}:`, error);
            throw error;
        }
    }

    // 根据ID获取目标点
    async getTargetById(targetId) {
        try {
            return await this.get(`/targets/${targetId}`);
        } catch (error) {
            Logger.error(`Failed to get target ${targetId}:`, error);
            throw error;
        }
    }

    // 上传地图文件
    async uploadMapFile(mapId, mapFile) {
        try {
            if (!mapFile) {
                throw new Error('Map file is required');
            }

            const formData = new FormData();
            formData.append('mapFile', mapFile);

            return await this.upload(`${this.endpoint}/${mapId}/file`, formData);
        } catch (error) {
            Logger.error(`Failed to upload map file for map ${mapId}:`, error);
            throw error;
        }
    }

    // Mock数据和方法（临时使用）
    getMockMaps() {
        return [
            {
                mapId: 'uuid-m1',
                mapName: '公园北区',
                mapDescription: '适合初级训练的开阔草地',
                targetCount: 6
            },
            {
                mapId: 'uuid-m2',
                mapName: '小区花园',
                mapDescription: '有更多互动元素的复杂环境',
                targetCount: 10
            },
            {
                mapId: 'uuid-m3',
                mapName: '室内训练场',
                mapDescription: '室内环境，适合恶劣天气时使用',
                targetCount: 4
            }
        ];
    }

    createMockMap(mapData) {
        return {
            ...mapData,
            mapId: `uuid-m${Date.now()}`,
            targetCount: 0
        };
    }
}

export default new MapsAPI();
