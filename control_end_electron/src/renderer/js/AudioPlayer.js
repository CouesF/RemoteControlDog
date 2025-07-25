/**
 * AudioPlayer.js
 * 
 * Handles WebSocket connection for audio streaming and plays the received audio
 * using the Web Audio API with an improved buffering strategy to prevent stuttering.
 */
export class AudioPlayer {
    constructor(wsUrl, options = {}) {
        this.wsUrl = wsUrl;
        this.sampleRate = options.sampleRate || 16000;
        this.websocket = null;
        this.audioContext = null;
        this.isConnected = false;
        this.actualPlaybackTimes = []; // 记录实际播放时间
        
        // 音频缓冲区设置
        this.bufferSize = options.bufferSize || 4; // 缓冲区大小，单位为音频块数
        this.audioQueue = []; // 音频缓冲队列
        this.isPlaying = false; // 是否正在播放
        this.lastMetadata = null; // 上一个元数据
        this.scheduledEndTime = 0; // 计划的结束时间
        
        // 性能监控
        this.bufferUnderrunCount = 0; // 缓冲区不足计数
        this.averageProcessingTime = 0; // 平均处理时间
        this.processedChunks = 0; // 处理的块数
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
                const receiveTime = Date.now();
                
                // 处理JSON元数据消息
                if (typeof event.data === 'string') {
                    try {
                        const metadata = JSON.parse(event.data);
                        this.lastMetadata = metadata;
                    } catch (e) {
                        console.error("Failed to parse metadata:", e);
                    }
                } 
                // 处理二进制音频数据
                else if (event.data instanceof ArrayBuffer) {
                    this.processAudioData(event.data, receiveTime);
                } else if (event.data instanceof Blob) {
                    event.data.arrayBuffer().then(arrayBuffer => {
                        this.processAudioData(arrayBuffer, receiveTime);
                    });
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

    processAudioData(arrayBuffer, receiveTime) {
        if (!this.lastMetadata) {
            console.warn("No metadata available for this audio chunk");
            return;
        }
        
        const timestamp = this.lastMetadata.timestamp;
        const networkLatency = receiveTime - timestamp;
        
        if (networkLatency > 300) {
            console.warn(`⚠️ High network latency: ${networkLatency}ms`);
        }
        
        const processStart = performance.now();
        
        // 将二进制数据转换为音频数据
        const int16Data = new Int16Array(arrayBuffer);
        const float32Data = new Float32Array(int16Data.length);

        for (let i = 0; i < int16Data.length; i++) {
            float32Data[i] = int16Data[i] / 32768.0;
        }

        const audioBuffer = this.audioContext.createBuffer(
            1,
            float32Data.length,
            this.sampleRate
        );

        audioBuffer.copyToChannel(float32Data, 0);
        
        // 将音频数据添加到缓冲队列
        this.queueAudioBuffer(audioBuffer, timestamp);
        
        // 计算处理时间并更新平均值
        const processingTime = performance.now() - processStart;
        this.processedChunks++;
        this.averageProcessingTime = (this.averageProcessingTime * (this.processedChunks - 1) + processingTime) / this.processedChunks;
        
        // 只在调试时打印详细日志
        if (this.processedChunks % 10 === 0) {
            console.log(`📊 Audio stats: Avg processing time: ${this.averageProcessingTime.toFixed(2)}ms, Buffer size: ${this.audioQueue.length}, Network latency: ${networkLatency}ms`);
        }
    }

    queueAudioBuffer(buffer, timestamp) {
        // 将音频缓冲区添加到队列
        this.audioQueue.push({
            buffer: buffer,
            timestamp: timestamp
        });
        
        // 如果缓冲区已经达到预设大小或者未处于播放状态，启动播放
        if ((this.audioQueue.length >= this.bufferSize && !this.isPlaying) || 
            (this.audioQueue.length === 1 && !this.isPlaying)) {
            this.startPlayback();
        }
        
        // 如果缓冲区过大，移除最旧的项防止内存增长过快
        const maxBufferSize = this.bufferSize * 3;
        if (this.audioQueue.length > maxBufferSize) {
            console.warn(`Buffer growing too large (${this.audioQueue.length}), trimming...`);
            this.audioQueue = this.audioQueue.slice(-this.bufferSize);
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
            // 缓冲区空了，等待更多数据
            this.isPlaying = false;
            this.bufferUnderrunCount++;
            console.warn(`Buffer underrun #${this.bufferUnderrunCount}`);
            return;
        }
        
        const audioItem = this.audioQueue.shift();
        const buffer = audioItem.buffer;
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        
        // 连接到分析器节点，然后到输出
        source.connect(this.analyser);
        
        const currentTime = this.audioContext.currentTime;
        let startTime;
        
        // 确定开始时间：如果这是连续播放，则从上一个结束时间开始
        if (this.scheduledEndTime > currentTime) {
            startTime = this.scheduledEndTime;
        } else {
            // 有缝隙，立即开始播放
            startTime = currentTime;
            
            // 如果发生了明显的缝隙，记录
            if (this.scheduledEndTime > 0 && currentTime - this.scheduledEndTime > 0.05) {
                console.warn(`Audio gap detected: ${((currentTime - this.scheduledEndTime) * 1000).toFixed(2)}ms`);
            }
        }
        
        // 计算这个缓冲区的持续时间
        const bufferDuration = buffer.duration;
        
        // 更新下一个缓冲区的计划开始时间
        this.scheduledEndTime = startTime + bufferDuration;
        
        // 启动播放
        source.start(startTime);
        
        // 记录延迟信息
        const playbackDelay = (startTime - currentTime) * 1000; // 转为毫秒
        const totalLatency = Date.now() - audioItem.timestamp + playbackDelay;
        
        // 只在调试或有问题时打印日志
        if (playbackDelay > 100 || totalLatency > 300) {
            console.log(`🎵 Audio playback: delay=${playbackDelay.toFixed(0)}ms, total latency=${totalLatency.toFixed(0)}ms`);
        }
        
        // 当这个缓冲区播放完毕时，安排下一个
        source.onended = () => {
            // 实际上我们不使用这个事件，因为它可能不可靠
            // 我们依赖计划的时间来安排下一个缓冲区
        };
        
        // 安排下一个缓冲区播放（使用定时器而不是onended事件）
        // 稍微提前安排，以确保无缝播放
        const schedulingAdvance = Math.min(bufferDuration * 0.5, 0.1); // 最多提前100ms或一半缓冲区时间
        const schedulingDelay = (bufferDuration - schedulingAdvance) * 1000;
        
        setTimeout(() => {
            this.playNextBuffer();
        }, schedulingDelay);
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
