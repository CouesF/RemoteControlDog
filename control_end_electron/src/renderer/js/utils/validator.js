// 数据验证工具
import { VALIDATION_RULES } from './constants.js';

export class ValidationError extends Error {
    constructor(field, message) {
        super(message);
        this.name = 'ValidationError';
        this.field = field;
    }
}

export class Validator {
    static validateParticipant(participant) {
        const errors = [];

        // 验证姓名
        if (!this.validateRequired(participant.participantName)) {
            errors.push(new ValidationError('participantName', '被试姓名不能为空'));
        } else if (!this.validateLength(participant.participantName, 
            VALIDATION_RULES.PARTICIPANT_NAME.minLength, 
            VALIDATION_RULES.PARTICIPANT_NAME.maxLength)) {
            errors.push(new ValidationError('participantName', '被试姓名长度必须在2-50个字符之间'));
        }

        // 验证年龄
        if (participant.year === null || participant.year === undefined) {
            errors.push(new ValidationError('year', '年龄不能为空'));
        } else if (!this.validateNumber(participant.year, 0, 18)) {
            errors.push(new ValidationError('year', '年龄必须在0-18岁之间'));
        }

        if (participant.month === null || participant.month === undefined) {
            errors.push(new ValidationError('month', '月龄不能为空'));
        } else if (!this.validateNumber(participant.month, 0, 11)) {
            errors.push(new ValidationError('month', '月龄必须在0-11个月之间'));
        }

        // 验证家长信息
        if (!this.validateRequired(participant.parentName)) {
            errors.push(new ValidationError('parentName', '家长姓名不能为空'));
        }

        if (!this.validateRequired(participant.parentPhone)) {
            errors.push(new ValidationError('parentPhone', '联系电话不能为空'));
        } else if (!this.validatePattern(participant.parentPhone, VALIDATION_RULES.PARENT_PHONE.pattern)) {
            errors.push(new ValidationError('parentPhone', '请输入有效的手机号码'));
        }

        return errors;
    }

    static validateMap(map) {
        const errors = [];

        if (!this.validateRequired(map.mapName)) {
            errors.push(new ValidationError('mapName', '地图名称不能为空'));
        } else if (!this.validateLength(map.mapName, 
            VALIDATION_RULES.MAP_NAME.minLength, 
            VALIDATION_RULES.MAP_NAME.maxLength)) {
            errors.push(new ValidationError('mapName', '地图名称长度必须在2-100个字符之间'));
        }

        return errors;
    }

    static validateTarget(target) {
        const errors = [];

        if (!this.validateRequired(target.targetName)) {
            errors.push(new ValidationError('targetName', '目标点名称不能为空'));
        }

        if (!target.pose || typeof target.pose !== 'object') {
            errors.push(new ValidationError('pose', '目标点位置信息无效'));
        } else {
            // 验证位置坐标
            if (!this.validateNumber(target.pose.position?.x)) {
                errors.push(new ValidationError('pose.position.x', 'X坐标必须是有效数字'));
            }
            if (!this.validateNumber(target.pose.position?.y)) {
                errors.push(new ValidationError('pose.position.y', 'Y坐标必须是有效数字'));
            }
            if (!this.validateNumber(target.pose.position?.z)) {
                errors.push(new ValidationError('pose.position.z', 'Z坐标必须是有效数字'));
            }
        }

        return errors;
    }

    static validateRequired(value) {
        if (value === null || value === undefined) {
            return false;
        }
        if (typeof value === 'string') {
            return value.trim() !== '';
        }
        if (typeof value === 'number') {
            return !isNaN(value);
        }
        return true;
    }

    static validateLength(value, min, max) {
        if (typeof value !== 'string') return false;
        return value.length >= min && value.length <= max;
    }

    static validateNumber(value, min = Number.NEGATIVE_INFINITY, max = Number.POSITIVE_INFINITY) {
        const num = Number(value);
        return !isNaN(num) && num >= min && num <= max;
    }

    static validatePattern(value, pattern) {
        if (typeof value !== 'string') return false;
        return pattern.test(value);
    }

    static validateEmail(email) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return this.validatePattern(email, emailPattern);
    }

    static validateUUID(uuid) {
        const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return this.validatePattern(uuid, uuidPattern);
    }
}
