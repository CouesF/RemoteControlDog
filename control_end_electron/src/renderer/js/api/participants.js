// 参与者相关API
import { BaseAPI } from './base.js';
import { API_ENDPOINTS } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';
import CONFIG from '../config.js';

class ParticipantsAPI extends BaseAPI {
    constructor() {
        super(CONFIG.API.BASE_URL);
        this.setTimeout(CONFIG.API.TIMEOUT);
        this.endpoint = API_ENDPOINTS.PARTICIPANTS;
    }

    // 获取所有参与者
    async getAll() {
        try {
            return await this.get(this.endpoint);
        } catch (error) {
            Logger.error('Failed to get participants:', error);
            throw error;
        }
    }

    // 根据ID获取参与者
    async getById(participantId) {
        try {
            return await this.get(`${this.endpoint}/${participantId}`);
        } catch (error) {
            Logger.error(`Failed to get participant ${participantId}:`, error);
            throw error;
        }
    }

    // 创建新参与者
    async create(participantData) {
        try {
            // 验证数据
            const errors = Validator.validateParticipant(participantData);
            if (errors.length > 0) {
                throw new Error(`Validation failed: ${errors.map(e => e.message).join(', ')}`);
            }

            return await this.post(this.endpoint, participantData);
        } catch (error) {
            Logger.error('Failed to create participant:', error);
            throw error;
        }
    }

    // 更新参与者
    async update(participantId, participantData) {
        try {
            // 验证数据
            const errors = Validator.validateParticipant(participantData);
            if (errors.length > 0) {
                throw new Error(`Validation failed: ${errors.map(e => e.message).join(', ')}`);
            }

            return await this.put(`${this.endpoint}/${participantId}`, participantData);
        } catch (error) {
            Logger.error(`Failed to update participant ${participantId}:`, error);
            throw error;
        }
    }

    // 删除参与者
    async delete(participantId) {
        try {
            await super.delete(`${this.endpoint}/${participantId}`);
            return true;
        } catch (error) {
            Logger.error(`Failed to delete participant ${participantId}:`, error);
            throw error;
        }
    }

    // 上传参与者图片
    async uploadImage(participantId, imageFile, imageType) {
        try {
            if (!imageFile || !imageType) {
                throw new Error('Image file and type are required');
            }

            const formData = new FormData();
            formData.append('imageFile', imageFile);
            formData.append('imageType', imageType);

            return await this.upload(`${this.endpoint}/${participantId}/images`, formData);
        } catch (error) {
            Logger.error(`Failed to upload image for participant ${participantId}:`, error);
            throw error;
        }
    }

    // 获取参与者图片
    async getImages(participantId) {
        try {
            return await this.get(`${this.endpoint}/${participantId}/images`);
        } catch (error) {
            Logger.error(`Failed to get images for participant ${participantId}:`, error);
            throw error;
        }
    }

    // 删除图片
    async deleteImage(imageId) {
        try {
            await super.delete(`/api/images/${imageId}`);
            return true;
        } catch (error) {
            Logger.error(`Failed to delete image ${imageId}:`, error);
            throw error;
        }
    }

    // Mock数据和方法（临时使用）
    getMockParticipants() {
        return [
            {
                participantId: 'uuid-p1',
                participantName: '张三',
                year: 5,
                month: 2,
                parentName: '张先生',
                parentPhone: '13800138001',
                diagnosticInfo: '发育迟缓',
                preferenceInfo: '喜欢蓝色和汽车',
            },
            {
                participantId: 'uuid-p2',
                participantName: '李四',
                year: 4,
                month: 8,
                parentName: '李女士',
                parentPhone: '13900139002',
                diagnosticInfo: '自闭症谱系障碍',
                preferenceInfo: '对声音敏感，喜欢安静',
            }
        ];
    }

    createMockParticipant(participantData) {
        return {
            ...participantData,
            participantId: `uuid-p${Date.now()}`
        };
    }
}

export default new ParticipantsAPI();
