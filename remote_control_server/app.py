#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程控制服务器 - Flask + WebSocket实现
用于远程控制Electron应用中的JA成功/失败按钮
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
import json
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'remote_control_dog_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# 简单的访问token
VALID_TOKEN = "remote_control_2024"

# 连接管理
connected_clients = {
    'web_clients': {},      # 网页客户端
    'electron_clients': {}  # Electron客户端
}

def verify_token(token):
    """验证访问token"""
    return token == VALID_TOKEN

def get_timestamp():
    """获取当前时间戳"""
    return int(time.time() * 1000)

def log_event(client_type, event, data=None):
    """记录事件日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{timestamp}] {client_type}: {event} - {data}")

@app.route('/')
def index():
    """主页面 - 需要token验证"""
    token = request.args.get('token', '')
    if not verify_token(token):
        return render_template('error.html', 
                             message="访问被拒绝：无效的访问令牌"), 403
    
    return render_template('control.html', token=token)

@app.route('/status')
def status():
    """系统状态接口"""
    return jsonify({
        'status': 'running',
        'connected_web_clients': len(connected_clients['web_clients']),
        'connected_electron_clients': len(connected_clients['electron_clients']),
        'timestamp': get_timestamp()
    })

@socketio.on('connect')
def handle_connect():
    """处理WebSocket连接"""
    client_id = request.sid
    log_event("SYSTEM", f"New connection attempt: {client_id}")

@socketio.on('auth')
def handle_auth(data):
    """处理客户端认证"""
    client_id = request.sid
    
    try:
        client_type = data.get('client_type', 'unknown')
        token = data.get('token', '')
        
        if not verify_token(token):
            log_event("AUTH", f"Authentication failed for {client_id}: invalid token")
            emit('auth_response', {
                'success': False,
                'message': '认证失败：无效的访问令牌',
                'timestamp': get_timestamp()
            })
            disconnect()
            return
        
        # 根据客户端类型进行分类存储
        if client_type == 'web':
            connected_clients['web_clients'][client_id] = {
                'connected_at': get_timestamp(),
                'last_activity': get_timestamp()
            }
        elif client_type == 'electron':
            connected_clients['electron_clients'][client_id] = {
                'connected_at': get_timestamp(),
                'last_activity': get_timestamp()
            }
        
        log_event("AUTH", f"Authentication successful for {client_type} client: {client_id}")
        emit('auth_response', {
            'success': True,
            'message': '认证成功',
            'client_id': client_id,
            'timestamp': get_timestamp()
        })
        
        # 广播连接状态更新
        broadcast_status_update()
        
    except Exception as e:
        log_event("ERROR", f"Authentication error for {client_id}: {str(e)}")
        emit('auth_response', {
            'success': False,
            'message': f'认证错误：{str(e)}',
            'timestamp': get_timestamp()
        })

@socketio.on('control_command')
def handle_control_command(data):
    """处理控制命令（来自网页客户端）"""
    client_id = request.sid
    
    try:
        # 验证客户端是否为已认证的网页客户端
        if client_id not in connected_clients['web_clients']:
            emit('command_response', {
                'success': False,
                'message': '未认证的客户端',
                'timestamp': get_timestamp()
            })
            return
        
        action = data.get('action', '')
        if action not in ['ja_success', 'ja_failure']:
            emit('command_response', {
                'success': False,
                'message': f'无效的操作：{action}',
                'timestamp': get_timestamp()
            })
            return
        
        # 更新客户端活动时间
        connected_clients['web_clients'][client_id]['last_activity'] = get_timestamp()
        
        # 构造转发给Electron的消息
        command_message = {
            'type': 'command',
            'action': action,
            'from_client': client_id,
            'timestamp': get_timestamp(),
            'data': data.get('data', {})
        }
        
        # 转发给所有已连接的Electron客户端
        electron_clients = list(connected_clients['electron_clients'].keys())
        if not electron_clients:
            emit('command_response', {
                'success': False,
                'message': '没有可用的Electron客户端',
                'timestamp': get_timestamp()
            })
            log_event("COMMAND", f"No Electron clients available for command: {action}")
            return
        
        # 发送命令到Electron客户端
        for electron_client_id in electron_clients:
            socketio.emit('remote_command', command_message, room=electron_client_id)
        
        log_event("COMMAND", f"Command '{action}' sent from web client {client_id} to {len(electron_clients)} Electron client(s)")
        
        # 向网页客户端确认命令已发送
        emit('command_response', {
            'success': True,
            'message': f'命令 "{action}" 已发送到 {len(electron_clients)} 个Electron客户端',
            'timestamp': get_timestamp()
        })
        
    except Exception as e:
        log_event("ERROR", f"Control command error from {client_id}: {str(e)}")
        emit('command_response', {
            'success': False,
            'message': f'命令处理错误：{str(e)}',
            'timestamp': get_timestamp()
        })

@socketio.on('command_result')
def handle_command_result(data):
    """处理命令执行结果（来自Electron客户端）"""
    client_id = request.sid
    
    try:
        # 验证客户端是否为已认证的Electron客户端
        if client_id not in connected_clients['electron_clients']:
            return
        
        # 更新客户端活动时间
        connected_clients['electron_clients'][client_id]['last_activity'] = get_timestamp()
        
        # 构造结果消息
        result_message = {
            'type': 'result',
            'action': data.get('action', ''),
            'success': data.get('success', False),
            'message': data.get('message', ''),
            'from_electron': client_id,
            'timestamp': get_timestamp()
        }
        
        # 广播结果给所有网页客户端
        web_clients = list(connected_clients['web_clients'].keys())
        for web_client_id in web_clients:
            socketio.emit('command_result', result_message, room=web_client_id)
        
        log_event("RESULT", f"Command result received from Electron {client_id}: {data}")
        
    except Exception as e:
        log_event("ERROR", f"Command result error from {client_id}: {str(e)}")

@socketio.on('ping')
def handle_ping(data):
    """处理心跳包"""
    client_id = request.sid
    
    # 更新客户端活动时间
    if client_id in connected_clients['web_clients']:
        connected_clients['web_clients'][client_id]['last_activity'] = get_timestamp()
    elif client_id in connected_clients['electron_clients']:
        connected_clients['electron_clients'][client_id]['last_activity'] = get_timestamp()
    
    emit('pong', {
        'timestamp': get_timestamp()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开连接"""
    client_id = request.sid
    
    # 从连接列表中移除客户端
    client_type = 'unknown'
    if client_id in connected_clients['web_clients']:
        del connected_clients['web_clients'][client_id]
        client_type = 'web'
    elif client_id in connected_clients['electron_clients']:
        del connected_clients['electron_clients'][client_id]
        client_type = 'electron'
    
    log_event("DISCONNECT", f"{client_type} client disconnected: {client_id}")
    
    # 广播连接状态更新
    broadcast_status_update()

def broadcast_status_update():
    """广播连接状态更新"""
    status_message = {
        'type': 'status_update',
        'web_clients_count': len(connected_clients['web_clients']),
        'electron_clients_count': len(connected_clients['electron_clients']),
        'timestamp': get_timestamp()
    }
    
    # 广播给所有客户端
    socketio.emit('status_update', status_message)

if __name__ == '__main__':
    logger.info("Starting Remote Control Server...")
    logger.info(f"Access URL: http://localhost:5000/?token={VALID_TOKEN}")
    
    # 启动服务器
    socketio.run(app, host='0.0.0.0', port=55000, debug=True)