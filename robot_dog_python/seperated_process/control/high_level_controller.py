
import time

# 延迟初始化的全局变量
sport = None

def ensure_sport_initialized():
    global sport
    if sport is None:
        from unitree_sdk2py.go2.sport.sport_client import SportClient
        sport = SportClient()
        sport.Init()


def run_highlevel_behavior():
    """高层模式初始化站立行为"""
    ensure_sport_initialized()
    print("[HighLevel] 设置为站立模式 (BalanceStand)...")
    sport.BalanceStand()
    time.sleep(0.5)

def update_navigation_target(x: float, y: float, r: float):
    """根据 DDS 指令发送速度命令 vx, vy, vyaw"""
    ensure_sport_initialized()
    print(f"[HighLevel] 接收到导航控制指令: x={x:.2f}, y={y:.2f}, r={r:.2f}")
    sport.Move(x, y, r)

def run_damp():
    """任何状态可进入阻尼模式"""
    ensure_sport_initialized()
    print("[DAMP] 进入阻尼模式 (Damp)...")
    sport.Damp()
    time.sleep(0.2)
