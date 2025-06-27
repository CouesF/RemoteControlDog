/**
 * ID格式化工具
 * 将长ID格式化为前4位...后4位的形式
 */

/**
 * 格式化ID显示，只显示前4位和后4位，中间用省略号
 * @param {string} id - 原始ID
 * @returns {string} 格式化后的ID
 */
export function formatIdDisplay(id) {
    if (!id || typeof id !== 'string') {
        return id || '';
    }
    
    // 如果ID长度小于等于8位，直接显示
    if (id.length <= 8) {
        return id;
    }
    
    // 取前4位和后4位，中间用省略号连接
    const prefix = id.substring(0, 4);
    const suffix = id.substring(id.length - 4);
    
    return `${prefix}...${suffix}`;
}

/**
 * 获取格式化的ID显示HTML
 * @param {string} id - 原始ID
 * @param {string} title - 完整ID（用于title属性）
 * @returns {string} 包含title属性的HTML
 */
export function formatIdDisplayWithTitle(id, title = null) {
    const displayId = formatIdDisplay(id);
    const fullId = title || id;
    
    return `<code title="${fullId}">${displayId}</code>`;
}
