// control_end_electron/test_camera_connection.js
// 测试摄像头UDP连接的脚本

const dgram = require('dgram');

// 测试配置
const TEST_CONFIG = {
    host: '118.31.58.101',
    port: 48991,
    localPort: 0
};

class CameraConnectionTest {
    constructor() {
        this.socket = null;
        this.isConnected = false;
    }

    async testConnection() {
        console.log('开始测试摄像头连接...');
        console.log(`目标地址: ${TEST_CONFIG.host}:${TEST_CONFIG.port}`);

        try {
            // 创建UDP socket
            this.socket = dgram.createSocket('udp4');

            this.socket.on('error', (err) => {
                console.error('Socket错误:', err);
            });

            this.socket.on('message', (msg, rinfo) => {
                console.log(`收到来自 ${rinfo.address}:${rinfo.port} 的消息:`, msg.length, '字节');
                this.handleMessage(msg, rinfo);
            });

            // 发送订阅请求
            await this.sendSubscribeRequest();

            // 等待响应
            console.log('等待服务器响应...');
            setTimeout(() => {
                this.cleanup();
            }, 10000); // 10秒后清理

        } catch (error) {
            console.error('测试失败:', error);
            this.cleanup();
        }
    }

    async sendSubscribeRequest() {
        const subscribeMessage = {
            timestamp: Date.now(),
            data: {
                request_type: 'subscribe',
                camera_ids: [0, 1, 2],
                session_id: 'test_session_' + Date.now()
            }
        };

        const messageJson = JSON.stringify(subscribeMessage);
        const messageBuffer = Buffer.from(messageJson, 'utf8');

        console.log('发送订阅请求:', messageJson);

        return new Promise((resolve, reject) => {
            this.socket.send(messageBuffer, TEST_CONFIG.port, TEST_CONFIG.host, (err) => {
                if (err) {
                    console.error('发送失败:', err);
                    reject(err);
                } else {
                    console.log('订阅请求已发送');
                    resolve();
                }
            });
        });
    }

    handleMessage(data, rinfo) {
        try {
            // 尝试解析为JSON
            const message = JSON.parse(data.toString('utf8'));
            console.log('解析的消息:', JSON.stringify(message, null, 2));

            if (message.data && message.data.message_type === 'video_frame') {
                console.log(`收到视频帧: 摄像头${message.data.camera_id}, 帧ID: ${message.data.frame_id}`);
            }

        } catch (error) {
            // 可能是分片数据或其他格式
            console.log('收到非JSON数据，长度:', data.length);
            
            // 尝试解析分片格式
            if (data.length >= 2) {
                try {
                    const headerSize = data.readUInt16BE(0);
                    if (data.length >= 2 + headerSize) {
                        const headerBytes = data.slice(2, 2 + headerSize);
                        const header = JSON.parse(headerBytes.toString('utf8'));
                        console.log('分片头部:', header);
                    }
                } catch (e) {
                    console.log('无法解析分片格式');
                }
            }
        }
    }

    cleanup() {
        console.log('清理连接...');
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        console.log('测试完成');
        process.exit(0);
    }
}

// 运行测试
const test = new CameraConnectionTest();
test.testConnection().catch(console.error);

// 处理中断信号
process.on('SIGINT', () => {
    console.log('\n收到中断信号，正在退出...');
    if (test) {
        test.cleanup();
    }
});
