/**
 * AudioPlayer.js
 * 
 * Optimized WebSocket audio streaming player with reduced latency and better performance.
 * Uses simplified buffering strategy to minimize audio stuttering.
 */
export class AudioPlayer {
    constructor(wsUrl, options = {}) {
        this.wsUrl = wsUrl;
        this.sampleRate = options.sampleRate || 16000;
        this.websocket = null;
        this.audioContext = null;
        this.isConnected = false;
        
        // 优化后的音频缓冲区设置 - 减少缓冲延迟
        this.bufferSize = options.bufferSize || 2; // 减少缓冲区大小
        this.audioQueue = [];
        this.isPlaying = false;
        this.scheduledEndTime = 0;
        this.nextStartTime = 0;
        
        // 性能监控
        this.bufferUnderrunCount = 0;
        this.averageProcessingTime = 0;
        this.processedChunks = 0;
        this.totalLatency = 0;
        
        // 优化设置
        this.minBufferTime = 0.05; // 最小缓冲时间50ms
        this.maxBufferTime = 0.2;  // 最大缓冲时间200ms
    }

    initAudio() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate,
                latencyHint: 'interactive',  // 优化延迟
            });
            
            console.log('AudioContext initialized:');
            console.log('- Sample rate:', this.audioContext.sampleRate);
            console.log('- Base latency:', this.audioContext.baseLatency);
            console.log('- Output latency:', this.audioContext.outputLatency);
            console.log('- State:', this.audioContext.state);
            
            // 创建一个分析器节点，用于监控音频输出
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 2048;
            this.analyser.connect(this.audioContext.destination);
            
            // 清空缓冲区和状态
            this.resetAudioState();
        }
    }
    
    resetAudioState() {
        this.audioQueue = [];
        this.isPlaying = false;
        this.scheduledEndTime = 0;
        this.bufferUnderrunCount = 0;
        this.averageProcessingTime = 0;
        this.processedChunks = 0;
        this.lastMetadata = null;
    }

    connect() {
        return new Promise((resolve, reject) => {
            if (this.isConnected) {
                return resolve();
            }

            this.websocket = new WebSocket(this.wsUrl);
            
            // 增加超时处理
            const connectionTimeout = setTimeout(() => {
                if (!this.isConnected) {
                    reject(new Error("WebSocket connection timeout"));
                }
            }, 5000);

            this.websocket.onopen = () => {
                console.log("Audio WebSocket connection established.");
                this.isConnected = true;
                this.initAudio();
                clearTimeout(connectionTimeout);
                resolve();
            };

            this.websocket.onmessage = (event) => {
                // 后端只发送二进制音频数据，直接处理
                if (event.data instanceof Blob) {
                    event.data.arrayBuffer().then(arrayBuffer => {
                        this.processAudioData(arrayBuffer);
                    });
                } else if (event.data instanceof ArrayBuffer) {
                    this.processAudioData(arrayBuffer);
                }
            };

            this.websocket.onerror = (error) => {
                console.error("WebSocket error:", error);
                clearTimeout(connectionTimeout);
                reject(error);
            };

            this.websocket.onclose = () => {
                console.log("Audio WebSocket connection closed.");
                this.isConnected = false;
                this.stop();
                clearTimeout(connectionTimeout);
            };
        });
    }

    processAudioData(arrayBuffer) {
        if (!this.audioContext || this.audioContext.state !== 'running') {
            console.warn('AudioContext not ready, skipping audio data');
            return;
        }

        const processStart = performance.now();
        
        try {
            // 快速转换：直接使用TypedArray视图，避免循环
            const int16Data = new Int16Array(arrayBuffer);
            const float32Data = new Float32Array(int16Data.length);
            
            // 优化的转换循环 - 批量处理
            for (let i = 0; i < int16Data.length; i++) {
                float32Data[i] = int16Data[i] * 0.000030517578125; // 1/32768 预计算
            }

            // 创建音频缓冲区
            const audioBuffer = this.audioContext.createBuffer(
                1,
                float32Data.length,
                this.sampleRate
            );

            audioBuffer.copyToChannel(float32Data, 0);
            
            // 添加到队列
            this.queueAudioBuffer(audioBuffer);
            
            // 性能统计
            const processingTime = performance.now() - processStart;
            this.processedChunks++;
            this.averageProcessingTime = (this.averageProcessingTime * (this.processedChunks - 1) + processingTime) / this.processedChunks;
            
            // 减少日志输出频率
            if (this.processedChunks % 50 === 0) {
                console.log(`📊 Audio performance: ${this.averageProcessingTime.toFixed(1)}ms, Queue: ${this.audioQueue.length}, Underruns: ${this.bufferUnderrunCount}`);
            }
        } catch (error) {
            console.error('Error processing audio data:', error);
        }
    }

    queueAudioBuffer(buffer) {
        const bufferDuration = buffer.duration;
        
        // 添加带时间戳的缓冲区
        this.audioQueue.push({
            buffer: buffer,
            duration: bufferDuration,
            timestamp: performance.now()
        });
        
        // 动态调整启动策略 - 减少延迟
        const shouldStart = !this.isPlaying && (
            this.audioQueue.length >= 1 || // 立即开始，减少延迟
            (this.audioQueue.length === 1 && this.bufferUnderrunCount > 3) // 如果之前有underrun，需要更多缓冲
        );
        
        if (shouldStart) {
            this.startPlayback();
        }
        
        // 防止缓冲区过大
        const maxBufferSize = Math.max(this.bufferSize * 2, 6);
        if (this.audioQueue.length > maxBufferSize) {
            console.warn(`Buffer overflow: ${this.audioQueue.length} > ${maxBufferSize}, dropping old audio`);
            this.audioQueue = this.audioQueue.slice(-Math.floor(maxBufferSize / 2));
        }
    }
    
    startPlayback() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }
        
        this.isPlaying = true;
        this.playNextBuffer();
    }
    
    playNextBuffer() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            this.bufferUnderrunCount++;
            if (this.bufferUnderrunCount % 5 === 1) { // 减少日志频率
                console.warn(`Buffer underrun #${this.bufferUnderrunCount}`);
            }
            return;
        }
        
        const audioItem = this.audioQueue.shift();
        const buffer = audioItem.buffer;
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        
        // 直接连接到destination，减少节点链路延迟
        source.connect(this.audioContext.destination);
        
        const currentTime = this.audioContext.currentTime;
        let startTime;
        
        // 优化启动时间计算
        if (this.scheduledEndTime > currentTime + 0.01) { // 添加小的容错时间
            startTime = this.scheduledEndTime;
        } else {
            // 立即播放或很小的延迟
            startTime = Math.max(currentTime, currentTime + 0.005); // 最小5ms延迟避免点击声
            
            // 只在significant gap时警告
            if (this.scheduledEndTime > 0 && currentTime - this.scheduledEndTime > 0.1) {
                console.warn(`Significant audio gap: ${((currentTime - this.scheduledEndTime) * 1000).toFixed(0)}ms`);
            }
        }
        
        // 更新计划结束时间
        this.scheduledEndTime = startTime + audioItem.duration;
        
        // 启动播放
        source.start(startTime);
        
        // 计算并记录延迟
        const latency = (startTime - currentTime) * 1000;
        this.totalLatency = (this.totalLatency * 0.9) + (latency * 0.1); // 指数平滑
        
        // 提前安排下一个缓冲区，使用递归调用而不是setTimeout来减少延迟
        const advance = Math.min(audioItem.duration * 0.8, 0.05); // 提前时间
        const nextCallDelay = Math.max((audioItem.duration - advance) * 1000, 10); // 最少10ms
        
        setTimeout(() => {
            this.playNextBuffer();
        }, nextCallDelay);
    }

    // 这些方法已经被上面的新实现替代，所以可以删除

    disconnect() {
        if (this.websocket) {
            this.websocket.onclose = null; // Prevent reconnection logic on manual disconnect
            this.websocket.close();
            this.websocket = null;
        }
        this.stop();
        this.isConnected = false;
        console.log("Audio player disconnected.");
    }

    stop() {
        // 停止所有播放
        this.resetAudioState();
        
        if (this.audioContext) {
            // 不关闭上下文，只是暂停当前活动
            // 频繁关闭和重新创建AudioContext可能导致资源泄漏
            if (this.audioContext.state === 'running') {
                this.audioContext.suspend().then(() => {
                    console.log("AudioContext suspended.");
                });
            }
        }
    }

    // 重启已暂停的音频上下文
    resume() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                console.log("AudioContext resumed.");
            });
        }
    }

    // 获取性能统计信息
    getPerformanceStats() {
        return {
            bufferSize: this.audioQueue.length,
            bufferUnderruns: this.bufferUnderrunCount,
            averageProcessingTime: this.averageProcessingTime,
            isPlaying: this.isPlaying,
            audioContextState: this.audioContext ? this.audioContext.state : 'closed'
        };
    }

    // 调整缓冲区大小（动态响应网络条件）
    setBufferSize(newSize) {
        if (newSize >= 1 && newSize <= 20) {
            this.bufferSize = newSize;
            console.log(`Audio buffer size adjusted to ${newSize} chunks`);
        }
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect in ${this.reconnectInterval / 1000}s... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect().catch(() => {}), this.reconnectInterval);
        } else {
            console.error("Max reconnection attempts reached.");
        }
    }
}
