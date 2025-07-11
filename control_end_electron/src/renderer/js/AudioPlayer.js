/**
 * AudioPlayer.js
 * 
 * Handles WebSocket connection for audio streaming and plays the received audio
 * using the Web Audio API.
 */
export class AudioPlayer {
    constructor(wsUrl, options = {}) {
        this.wsUrl = wsUrl;
        this.sampleRate = options.sampleRate || 16000;
        this.websocket = null;
        this.audioContext = null;
        this.isConnected = false;
        this.actualPlaybackTimes = []; // 记录实际播放时间
    }

    initAudio() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate,
                latencyHint: 'interactive',
            });
            
            console.log('AudioContext initialized:');
            console.log('- Sample rate:', this.audioContext.sampleRate);
            console.log('- Base latency:', this.audioContext.baseLatency);
            console.log('- Output latency:', this.audioContext.outputLatency);
            console.log('- State:', this.audioContext.state);
        }
    }

    connect() {
        return new Promise((resolve, reject) => {
            if (this.isConnected) {
                return resolve();
            }

            this.websocket = new WebSocket(this.wsUrl);

            this.websocket.onopen = () => {
                console.log("Audio WebSocket connection established.");
                this.isConnected = true;
                this.initAudio();
                resolve();
            };

            this.websocket.onmessage = (event) => {
                const receiveTime = Date.now();
                
                if (event.data instanceof ArrayBuffer) {
                    this.processRawAudioWithTimestamp(event.data, receiveTime);
                } else if (event.data instanceof Blob) {
                    event.data.arrayBuffer().then(arrayBuffer => {
                        this.processRawAudioWithTimestamp(arrayBuffer, receiveTime);
                    });
                }
            };

            this.websocket.onerror = (error) => {
                console.error("WebSocket error:", error);
                reject(error);
            };

            this.websocket.onclose = () => {
                console.log("Audio WebSocket connection closed.");
                this.isConnected = false;
                this.stop();
            };
        });
    }

    processRawAudioWithTimestamp(arrayBuffer, receiveTime) {
        // 提取时间戳（前8字节）
        const timestampBytes = new Uint8Array(arrayBuffer, 0, 8);
        const timestamp = this.bytesToTimestamp(timestampBytes);
        
        // 提取音频数据（剩余字节）
        const audioData = arrayBuffer.slice(8);
        
        const networkLatency = receiveTime - timestamp;
        console.log(`📡 Network latency: ${networkLatency}ms`);
        
        const processStart = performance.now();
        this.processRawAudio(audioData, timestamp);
        const processEnd = performance.now();
        console.log(`⚡ Audio processing time: ${(processEnd - processStart).toFixed(2)}ms`);
    }

    bytesToTimestamp(bytes) {
        let timestamp = 0;
        for (let i = 0; i < 8; i++) {
            timestamp += bytes[i] * Math.pow(2, i * 8);
        }
        return timestamp;
    }

    processRawAudio(arrayBuffer, originalTimestamp) {
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
        this.playImmediately(audioBuffer, originalTimestamp);
    }

    playImmediately(buffer, originalTimestamp) {
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        
        const currentTime = this.audioContext.currentTime;
        const startTime = currentTime + 0.01; // 立即播放，只留10ms缓冲
        
        console.log(`🎵 Scheduling play: currentTime=${currentTime.toFixed(3)}, startTime=${startTime.toFixed(3)}`);
        
        source.start(startTime);
        
        // 记录实际播放时间用于延迟计算
        const actualPlayTime = Date.now() + (startTime - currentTime) * 1000;
        const totalLatency = actualPlayTime - originalTimestamp;
        
        console.log(`📊 Total latency: ${totalLatency.toFixed(0)}ms (from capture to play)`);
        
        // 如果延迟过高，尝试立即播放
        if (totalLatency > 500) {
            console.warn(`🚨 High latency detected: ${totalLatency}ms, trying immediate play`);
            const immediateSource = this.audioContext.createBufferSource();
            immediateSource.buffer = buffer;
            immediateSource.connect(this.audioContext.destination);
            immediateSource.start(0); // 立即播放
        }
    }

    schedulePlay(buffer) {
        this.audioQueue.push(buffer);
        if (!this.isPlaying) {
            this.playQueue();
        }
    }

    playQueue() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }

        this.isPlaying = true;
        const buffer = this.audioQueue.shift();
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        source.start();
        source.onended = () => this.playQueue();
    }

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
        if (this.audioContext) {
            this.audioContext.close().then(() => {
                this.audioContext = null;
                console.log("AudioContext closed.");
            });
        }
        this.audioQueue = [];
        this.isPlaying = false;
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
