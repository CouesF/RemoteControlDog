# dds_data_structure.py

"""
此文件定义了机器人狗项目中所有模块间通过DDS通信所使用的数据结构。
每个数据结构都使用 @dataclass 装饰器，并继承自 IdlStruct，
以便在Python中方便地创建和使用，同时能被CycloneDDS序列化进行网络传输。
"""

from dataclasses import dataclass, field
from cyclonedds.idl import IdlStruct
from cyclonedds.idl.annotations import key
from enum import IntEnum
from typing import List

# --------------------------------------------------------------------------
# 模块: main_dog_controller
# 订阅主题: DogMotion
# 描述: 用于接收对机器人狗身体和头部的控制指令。
# --------------------------------------------------------------------------

class LegID(IntEnum):
    """机器人腿的ID枚举"""
    FR = 0  # 右前腿 (Front Right)
    FL = 1  # 左前腿 (Front Left)
    RR = 2  # 右后腿 (Rear Right)
    RL = 3  # 左后腿 (Rear Left)


class MotionMode(IntEnum):
    """
    V2版本的运动控制模式枚举，语义更清晰。
    """
    IDLE = 0                    # 空闲/失能模式
    HIGH_LEVEL_VELOCITY = 1     # 高级运控: 控制机器人整体的速度和姿态
    LOW_LEVEL_STAND = 2         # 底层运控: 强制进入站立姿态并锁定关节
    LOW_LEVEL_SINGLE_LEG = 3    # 底层运控: 控制单条腿的运动


class ExpressionCommand(IntEnum):
    """表情控制指令枚举"""
    NORMAL = 0      # 正常
    HAPPY = 1       # 开心
    SAD = 2         # 难过

@dataclass
class LowLevelControl(IdlStruct, typename="LowLevelControl"):
    """
    底层单腿控制的详细参数。
    仅在 motion_mode 为 LOW_LEVEL_SINGLE_LEG 时有效。
    """
    # --- 目标腿控制 ---
    # 要控制的目标腿ID
    target_leg: LegID = LegID.FR
    
    # 目标腿的期望关节角度 [髋关节, 大腿关节, 小腿关节] (弧度制)
    # 这个字段也可以根据你的坐标系定义为末端点在身体坐标系下的 (x, y, z) 坐标
    target_q: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # --- 稳定性控制 (可选) ---
    # 为了抬起一条腿，可能需要先移动另一条腿来稳定重心
    # 需要调整姿态的稳定腿ID (如果不需要，可以设为与target_leg相同或一个无效值)
    stabilizing_leg: LegID = LegID.FL
    
    # 稳定腿在身体坐标系下的位置偏移量 [x_offset, y_offset, z_offset]
    # 例如，让左前腿往外侧移动一点以增加支撑面
    stabilizing_offset: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # --- PD 控制参数 ---
    # 允许通过DDS动态调整控制刚度，这在调试时非常有用
    # 对应 go2_low_level.cpp 中的 Kp, Kd
    kp: List[float] = field(default_factory=lambda: [5.0, 5.0, 5.0])
    kd: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])

@dataclass
class BodyControl(IdlStruct, typename="BodyControl"):
    """
    机器人狗运动控制指令结构体 (版本2)。
    """
    # 时间戳，用于同步和调试
    timestamp: int = 0

    # V2版本的运动控制模式
    mode: MotionMode = MotionMode.IDLE

    # --- 高级速度控制指令 ---
    # [前进/后退速度, 左/右平移速度, 转向角速度]
    # 仅在 mode 为 HIGH_LEVEL_VELOCITY 时有效
    velocity_command: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # --- 底层单腿控制指令 ---
    # 仅在 mode 为 LOW_LEVEL_SINGLE_LEG 时有效
    low_level_control: LowLevelControl = field(default_factory=LowLevelControl)
    


@dataclass
class HeadControl(IdlStruct, typename="HeadControl"):
    # --- 头部控制 ---
    # 头部角度控制: [俯仰角, 偏航角] rad 
    head_angles: List[float] = field(default_factory=lambda: [0.0, 0.0])

    # 表情控制
    expression: ExpressionCommand = ExpressionCommand.NORMAL

# --------------------------------------------------------------------------
# 模块: main_dog_status
# 发布主题: DogStatus
# 描述: 用于发布机器人狗自身的硬件状态信息。
# --------------------------------------------------------------------------


# ... (keep all your existing classes like BodyControl, HeadControl, etc.) ...

# NEW: for detailed Jetson stats

@dataclass
class JetsonTemperatures(IdlStruct, typename="JetsonTemperatures"):
    """Holds all temperature sensor readings from the Jetson."""
    cpu: float = 0.0  # Celsius
    gpu: float = 0.0
    soc0: float = 0.0
    soc1: float = 0.0
    soc2: float = 0.0
    cv0: float = 0.0
    cv1: float = 0.0
    cv2: float = 0.0
    tj: float = 0.0 # Thermal Zone Junction

@dataclass
class JetsonPower(IdlStruct, typename="JetsonPower"):
    """Holds all power consumption readings from the Jetson."""
    cpu_gpu_cv: float = 0.0 # mW
    soc: float = 0.0 # mW
    vdd_inn: float = 0.0 # mW
    nv_power_total: float = 0.0 # mW (from NV Power module)

@dataclass
class JetsonHardware(IdlStruct, typename="JetsonHardware"):
    """Holds other miscellaneous hardware stats."""
    disk_usage_percent: float = 0.0
    emc_usage_percent: float = 0.0 # Memory Controller
    fan_speed_percent: float = 0.0
    uptime_seconds: int = 0
    jetson_clocks_on: bool = False


# NOW, UPDATE THE DogStatus CLASS TO INCLUDE EVERYTHING

@dataclass
class DogStatus(IdlStruct, typename="DogStatus"):
    """
    机器人狗状态信息结构体 (V2 - Unified Version)。
    """
    # Original Fields
    battery_percent: float = 0.0
    memory_usage_percent: float = 0.0
    gpu_usage_percent: float = 0.0
    cpu_usage_percent: float = 0.0
    timestamp_ns: int = 0

    # --- NEW: Robot Motion/Control Mode ---
    # From MotionSwitcherClient.CheckMode()
    robot_mode_form: str = ""
    robot_mode_name: str = ""

    # --- NEW: Detailed Jetson Stats (Nested) ---
    # --- CORRECTED: Use String Forward References for all custom structs ---
    temperatures: 'JetsonTemperatures' = field(default_factory=JetsonTemperatures)
    power: 'JetsonPower' = field(default_factory=JetsonPower)
    hardware: 'JetsonHardware' = field(default_factory=JetsonHardware)

    # --- EXPANDED: Full unrolled motor state fields for 12 motors ---
    # Each motor now has 9 fields based on _MotorState_.py

    # Motor 0 (FR_hip)
    m0_mode: int = 0; m0_q: float = 0.0; m0_dq: float = 0.0; m0_ddq: float = 0.0
    m0_tau_est: float = 0.0; m0_temperature: int = 0; m0_lost: int = 0
    m0_reserve0: int = 0; m0_reserve1: int = 0
    # Motor 1 (FR_thigh)
    m1_mode: int = 0; m1_q: float = 0.0; m1_dq: float = 0.0; m1_ddq: float = 0.0
    m1_tau_est: float = 0.0; m1_temperature: int = 0; m1_lost: int = 0
    m1_reserve0: int = 0; m1_reserve1: int = 0
    # Motor 2 (FR_calf)
    m2_mode: int = 0; m2_q: float = 0.0; m2_dq: float = 0.0; m2_ddq: float = 0.0
    m2_tau_est: float = 0.0; m2_temperature: int = 0; m2_lost: int = 0
    m2_reserve0: int = 0; m2_reserve1: int = 0
    # Motor 3 (FL_hip)
    m3_mode: int = 0; m3_q: float = 0.0; m3_dq: float = 0.0; m3_ddq: float = 0.0
    m3_tau_est: float = 0.0; m3_temperature: int = 0; m3_lost: int = 0
    m3_reserve0: int = 0; m3_reserve1: int = 0
    # Motor 4 (FL_thigh)
    m4_mode: int = 0; m4_q: float = 0.0; m4_dq: float = 0.0; m4_ddq: float = 0.0
    m4_tau_est: float = 0.0; m4_temperature: int = 0; m4_lost: int = 0
    m4_reserve0: int = 0; m4_reserve1: int = 0
    # Motor 5 (FL_calf)
    m5_mode: int = 0; m5_q: float = 0.0; m5_dq: float = 0.0; m5_ddq: float = 0.0
    m5_tau_est: float = 0.0; m5_temperature: int = 0; m5_lost: int = 0
    m5_reserve0: int = 0; m5_reserve1: int = 0
    # Motor 6 (RR_hip)
    m6_mode: int = 0; m6_q: float = 0.0; m6_dq: float = 0.0; m6_ddq: float = 0.0
    m6_tau_est: float = 0.0; m6_temperature: int = 0; m6_lost: int = 0
    m6_reserve0: int = 0; m6_reserve1: int = 0
    # Motor 7 (RR_thigh)
    m7_mode: int = 0; m7_q: float = 0.0; m7_dq: float = 0.0; m7_ddq: float = 0.0
    m7_tau_est: float = 0.0; m7_temperature: int = 0; m7_lost: int = 0
    m7_reserve0: int = 0; m7_reserve1: int = 0
    # Motor 8 (RR_calf)
    m8_mode: int = 0; m8_q: float = 0.0; m8_dq: float = 0.0; m8_ddq: float = 0.0
    m8_tau_est: float = 0.0; m8_temperature: int = 0; m8_lost: int = 0
    m8_reserve0: int = 0; m8_reserve1: int = 0
    # Motor 9 (RL_hip)
    m9_mode: int = 0; m9_q: float = 0.0; m9_dq: float = 0.0; m9_ddq: float = 0.0
    m9_tau_est: float = 0.0; m9_temperature: int = 0; m9_lost: int = 0
    m9_reserve0: int = 0; m9_reserve1: int = 0
    # Motor 10 (RL_thigh)
    m10_mode: int = 0; m10_q: float = 0.0; m10_dq: float = 0.0; m10_ddq: float = 0.0
    m10_tau_est: float = 0.0; m10_temperature: int = 0; m10_lost: int = 0
    m10_reserve0: int = 0; m10_reserve1: int = 0
    # Motor 11 (RL_calf)
    m11_mode: int = 0; m11_q: float = 0.0; m11_dq: float = 0.0; m11_ddq: float = 0.0
    m11_tau_est: float = 0.0; m11_temperature: int = 0; m11_lost: int = 0
    m11_reserve0: int = 0; m11_reserve1: int = 0


# --------------------------------------------------------------------------
# 模块: main_cam_processing
# 订阅主题: CamControl
# 发布主题: CamResult
# 描述: 用于控制相机参数并发布图像处理结果。
# --------------------------------------------------------------------------

@dataclass
class CamControl(IdlStruct, typename="CamControl"):
    """
    相机控制指令结构体。
    """
    # 是否启用相机畸变校正
    enable_distortion_correction: bool = True

    # 亮度调整 (-1.0 ~ 1.0, 0为不调整)
    brightness: float = 0.0

    # 对比度调整 (-1.0 ~ 1.0, 0为不调整)
    contrast: float = 0.0


@dataclass
class CamResult(IdlStruct, typename="CamResult"):
    """
    相机处理结果结构体，主要用于目标定位。
    """
    # 时间戳
    timestamp: int = 0

    # 是否检测到目标
    target_detected: bool = False

    # 目标位置 (方向向量 [x, y, z] + 距离)
    # 方向向量是相对于相机坐标系的单位向量
    direction_vector: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    distance: float = 0.0


# --------------------------------------------------------------------------
# 模块: main_speech_synthesis
# 订阅主题: SpeechControl
# 描述: 用于接收文本转语音(TTS)的控制指令。
# --------------------------------------------------------------------------

@dataclass
class SpeechControl(IdlStruct, typename="SpeechControl"):
    """
    语音合成控制结构体。
    """
    # 需要转换为语音的文本内容
    text_to_speak: str = ""

    # 是否立即停止当前正在播报的语音
    stop_speaking: bool = False
    
    # 音量控制（范围建议 0 ~ 100）
    volume: int = 20


@dataclass
class SimpleIntTest(IdlStruct, typename="SimpleIntTest"):
    """
    int类型数据 (测试用)
    """
    command_id: int = 0
    value: int = 123


@dataclass
class RaiseLegCommand(IdlStruct, typename="RaiseLegCommand"):
    """
    抬腿动作指令结构体 (简化版，测试用)
    """
    command_id: int = 0        # 0 = 空闲, 1 = 执行抬腿动作
    leg_index: int = 0         # 0 = FR, 1 = FL, 2 = RR, 3 = RL
    hold_time_ms: int = 1000   # 抬腿持续时间（单位：毫秒）
