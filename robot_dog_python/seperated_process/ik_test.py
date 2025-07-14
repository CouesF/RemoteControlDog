import numpy as np

def find_angles(x, y):
    R = np.hypot(x, y)
    results = []

    if abs(R) > 2:
        print("无解：|x|^2 + |y|^2 超出2的平方，几何上无解")
        return results

    # φ 的计算
    phi = np.arctan2(y, x)

    # 计算可能的 c 值
    for sign in [+1, -1]:
        try:
            acos_val = np.arccos(R / 2)
        except ValueError:
            continue  # 非法情况

        c = phi + sign * acos_val

        cos_c = np.cos(c)
        sin_c = np.sin(c)

        cos_a = x - cos_c
        sin_a = -(y - sin_c)

        # 注意此时 (cos_a, sin_a) 不一定是单位向量，需要归一化
        norm = np.hypot(cos_a, sin_a)
        if norm == 0:
            continue
        cos_a /= norm
        sin_a /= norm

        a = np.arctan2(sin_a, cos_a)
        b = a + c

        # 输出（弧度 & 角度）
        results.append({
            'a_rad': a,
            'b_rad': b,
            'a_deg': np.degrees(a),
            'b_deg': np.degrees(b),
        })

    return results

# ==== 测试例子 ====
if __name__ == "__main__":
    x = float(input("输入 x: "))
    y = float(input("输入 y: "))

    results = find_angles(x, y)
    if not results:
        print("没有解")
    else:
        for idx, res in enumerate(results):
            print(f"\n解 {idx+1}:")
            print(f"  a = {res['a_rad']:.6f} 弧度, {res['a_deg']:.2f}°")
            print(f"  b = {res['b_rad']:.6f} 弧度, {res['b_deg']:.2f}°")
