# Notification系统测试指南

## 🎯 修复内容

本次修复解决了Windows上notification无法自动消失的问题，通过完全自定义的NotificationManager替换了依赖Bootstrap JavaScript的实现。

## 🔧 主要改动

1. **新增**: `NotificationManager.js` - 跨平台兼容的通知管理器
2. **修改**: `BasePage.js` - 统一notification API
3. **修改**: `MapBuilder.js` - 移除自定义notification实现
4. **修改**: `app.js` - 应用启动时初始化NotificationManager
5. **更新**: `custom.css` - 移除旧的notification样式

## 🧪 测试步骤

### 1. 基本功能测试

在浏览器开发者控制台中执行以下代码测试：

```javascript
// 测试成功通知
window.NotificationManager.success('测试成功', '这是一个成功消息');

// 测试警告通知
window.NotificationManager.warning('测试警告', '这是一个警告消息');

// 测试错误通知
window.NotificationManager.error('测试错误', '这是一个错误消息');

// 测试信息通知
window.NotificationManager.info('测试信息', '这是一个信息消息');
```

### 2. 自动消失功能测试

```javascript
// 测试默认1.5秒自动消失
window.NotificationManager.success('自动消失测试', '1.5秒后应该自动消失');

// 测试自定义时间（3秒）
window.NotificationManager.info('长时间显示', '3秒后消失', { duration: 3000 });

// 测试不自动消失
window.NotificationManager.warning('手动关闭', '需要手动关闭', { duration: 0 });
```

### 3. 多个通知测试

```javascript
// 快速创建多个通知测试队列管理
for(let i = 1; i <= 8; i++) {
    setTimeout(() => {
        window.NotificationManager.info(`通知 ${i}`, `这是第${i}个通知`);
    }, i * 200);
}
```

### 4. 位置和尺寸测试

```javascript
// 验证左侧显示位置
window.NotificationManager.info('位置测试', '应该显示在屏幕左上角');

// 验证紧凑尺寸
window.NotificationManager.success('尺寸测试', '应该比之前更紧凑');
```

### 5. 鼠标悬停测试

1. 显示一个通知：`window.NotificationManager.success('悬停测试', '鼠标悬停可暂停自动关闭');`
2. 在通知消失前将鼠标悬停在通知上
3. 验证通知暂停消失
4. 移开鼠标，验证通知继续倒计时并消失

### 6. 页面功能集成测试

1. **被试管理页面**:
   - 添加新被试 → 应显示成功通知
   - 删除被试 → 应显示成功通知
   - 表单验证失败 → 应显示警告通知

2. **地图管理页面**:
   - 创建新地图 → 应显示成功通知
   - 删除地图 → 应显示成功通知
   - 操作失败 → 应显示错误通知

3. **地图构建页面**:
   - 添加目标点 → 应显示成功通知
   - 删除目标点 → 应显示成功通知
   - 截图失败 → 应显示错误通知

## ✅ 验收标准

### 显示效果
- [ ] 通知显示在屏幕左上角（left: 20px, top: 20px）
- [ ] 容器宽度为280px（比之前的350px更紧凑）
- [ ] 通知从左侧滑入（translateX从-100%到0）
- [ ] 整体尺寸更紧凑（较小的padding、字体、图标）

### Windows兼容性
- [ ] 通知能正常显示
- [ ] 通知能在1.5秒后自动消失
- [ ] 关闭按钮能正常工作
- [ ] 鼠标悬停暂停功能正常
- [ ] 动画流畅无卡顿

### Mac兼容性
- [ ] 所有功能与Windows表现一致
- [ ] 无性能问题

### 通用功能
- [ ] 支持4种通知类型（success, warning, error, info）
- [ ] 支持自定义显示时间
- [ ] 支持手动关闭
- [ ] 最多同时显示5个通知
- [ ] 进度条动画正常
- [ ] 响应式设计在移动端正常

## 🐛 故障排除

### 如果通知不显示
1. 检查浏览器控制台是否有JavaScript错误
2. 确认`window.NotificationManager`已正确初始化
3. 验证CSS样式是否正确加载

### 如果动画不流畅
1. 检查CSS `transition`是否被其他样式覆盖
2. 确认浏览器支持硬件加速
3. 验证`will-change`属性是否生效

### 如果在Windows上仍有问题
1. 检查Electron版本兼容性
2. 验证CSS前缀是否完整
3. 确认事件绑定是否正确

## 📱 移动端测试

在小屏幕设备上：
- [ ] 通知显示位置正确（顶部全宽）
- [ ] 动画方向正确（从顶部滑入）
- [ ] 触摸操作正常

## 🚀 性能验证

- [ ] 大量通知时无内存泄漏
- [ ] 动画帧率稳定在60fps
- [ ] DOM元素能正确清理

---

**注意**: 测试时建议在Windows和Mac两个平台上都进行验证，确保完全的跨平台兼容性。