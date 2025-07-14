#!/usr/bin/env python3
"""
2-link inverse kinematics
坐标系: A(0,0) 为原点;  x 向右, y 向下
"""

import sys, numpy as np

# ─── 1. 机械参数 ────────────────────────────────────────────────────
L = 1.0  # 连杆长度

# 关节限位 (弧度)
θ1_min, θ1_max = np.deg2rad([-90, 200])
θ2_min, θ2_max = np.deg2rad([ 48, 156])

# ─── 2. 逆运动学核心 ────────────────────────────────────────────────
def ik(xC: float, yC: float):
    dx, dy = xC, yC
    d = np.hypot(dx, dy)
    if d > 2*L or d < 1e-9:
        return None

    a = d / 2.0
    h2 = L*L - a*a
    if h2 < 0:
        return None
    h = np.sqrt(h2)

    mx, my = dx/2, dy/2
    ux, uy = dx/d, dy/d
    px, py = -uy, ux

    for s in (+1, -1):
        xB = mx + s*h*px
        yB = my + s*h*py

        θ1 = np.arctan2(-yB, xB)                       # 注意 y 向下
        θ2 = np.arctan2(-(yC - yB), xC - xB) - np.arctan2(-yB, xB)
        θ2 = (θ2 + np.pi) % (2*np.pi) - np.pi

        if θ1_min <= θ1 <= θ1_max and θ2_min <= θ2 <= θ2_max:
            return θ1, θ2
    return None

# ─── 3. CLI ───────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 3:
        print("用法:  python3 ik_from_A.py <xC> <yC>")
        return

    try:
        xC = float(sys.argv[1])
        yC = float(sys.argv[2])
    except ValueError:
        print("请输入数字坐标, 例如:  python3 ik_from_A.py 0.4 0.2")
        return

    res = ik(xC, yC)
    if res is None:
        print("无效坐标")
    else:
        θ1, θ2 = res
        print(f"θ1 = {θ1:.6f} rad,  θ2 = {-θ2:.6f} rad")  # 仅输出时取负号

if __name__ == "__main__":
    main()
