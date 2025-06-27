#!/usr/bin/env python3
"""
WOZ系统API测试脚本
"""
import requests
import json
import time
from pathlib import Path

# API配置
BASE_URL = "http://118.31.58.101:48995"  # 根据系统规则，后端8995对应前端48995
API_PREFIX = "/api"

def test_api_connection():
    """测试API连接"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API连接成功")
            print(f"健康检查响应: {response.json()}")
            return True
        else:
            print(f"❌ API连接失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API连接异常: {e}")
        return False

def test_maps_api():
    """测试地图API"""
    print("\n=== 测试地图API ===")
    
    # 1. 获取所有地图
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/maps")
        if response.status_code == 200:
            maps = response.json()
            print(f"✅ 获取地图列表成功: {len(maps)} 个地图")
        else:
            print(f"❌ 获取地图列表失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 获取地图列表异常: {e}")
        return False
    
    # 2. 创建新地图
    try:
        map_data = {
            "mapName": "测试地图",
            "mapDescription": "这是一个测试地图"
        }
        response = requests.post(f"{BASE_URL}{API_PREFIX}/maps", json=map_data)
        if response.status_code == 201:
            new_map = response.json()
            map_id = new_map["mapId"]
            print(f"✅ 创建地图成功: {map_id}")
            return map_id
        else:
            print(f"❌ 创建地图失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 创建地图异常: {e}")
        return None

def test_targets_api(map_id):
    """测试目标点API"""
    if not map_id:
        print("❌ 无法测试目标点API: 没有有效的地图ID")
        return
    
    print(f"\n=== 测试目标点API (地图ID: {map_id}) ===")
    
    # 1. 获取地图的目标点
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/maps/{map_id}/targets")
        if response.status_code == 200:
            targets = response.json()
            print(f"✅ 获取目标点列表成功: {len(targets)} 个目标点")
        else:
            print(f"❌ 获取目标点列表失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取目标点列表异常: {e}")
        return
    
    # 2. 创建新目标点
    try:
        target_data = {
            "targetName": "测试目标点1",
            "description": "这是第一个测试目标点",
            "pose": json.dumps({
                "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                "orientation": {"w": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0}
            })
        }
        response = requests.post(f"{BASE_URL}{API_PREFIX}/maps/{map_id}/targets", data=target_data)
        if response.status_code == 201:
            target1 = response.json()
            target1_id = target1["targetId"]
            print(f"✅ 创建目标点1成功: {target1_id}")
        else:
            print(f"❌ 创建目标点1失败: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"❌ 创建目标点1异常: {e}")
        return
    
    # 3. 创建第二个目标点
    try:
        target_data = {
            "targetName": "测试目标点2",
            "description": "这是第二个测试目标点",
            "pose": json.dumps({
                "position": {"x": 3.0, "y": 4.0, "z": 0.0},
                "orientation": {"w": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0}
            })
        }
        response = requests.post(f"{BASE_URL}{API_PREFIX}/maps/{map_id}/targets", data=target_data)
        if response.status_code == 201:
            target2 = response.json()
            target2_id = target2["targetId"]
            print(f"✅ 创建目标点2成功: {target2_id}")
        else:
            print(f"❌ 创建目标点2失败: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"❌ 创建目标点2异常: {e}")
        return
    
    # 4. 测试顺序调整
    try:
        order_data = {
            "targetIds": [target2_id, target1_id]  # 交换顺序
        }
        response = requests.put(f"{BASE_URL}{API_PREFIX}/maps/{map_id}/targets/order", json=order_data)
        if response.status_code == 200:
            print("✅ 目标点顺序调整成功")
        else:
            print(f"❌ 目标点顺序调整失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ 目标点顺序调整异常: {e}")
    
    # 5. 验证顺序
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/maps/{map_id}/targets")
        if response.status_code == 200:
            targets = response.json()
            print("✅ 验证目标点顺序:")
            for i, target in enumerate(targets):
                print(f"  {i+1}. {target['targetName']} (sequence: {target['sequence']})")
        else:
            print(f"❌ 验证目标点顺序失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证目标点顺序异常: {e}")

def main():
    """主测试函数"""
    print("🚀 开始测试WOZ系统API")
    print(f"测试目标: {BASE_URL}")
    
    # 测试连接
    if not test_api_connection():
        print("\n❌ API连接失败，请检查后端是否正常运行")
        print("启动命令: python robot_dog_python/start_woz_backend.py")
        return
    
    # 测试地图API
    map_id = test_maps_api()
    
    # 测试目标点API
    test_targets_api(map_id)
    
    print("\n🎉 API测试完成")
    print("\n📖 API文档地址: http://118.31.58.101:48995/docs")

if __name__ == "__main__":
    main()
