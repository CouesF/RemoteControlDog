
## 功能：实现文本转语音
功能描述：将文本转换成语音（且包含停止语音和调整音量功能）
使用方法：
先激活env_unitree虚拟环境
新开terminal
python /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/main_speech_synthesis.py

（运行测试）
先激活env_unitree虚拟环境
新开terminal
python /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/speech_test.py

## 功能：获取狗状态信息
功能描述：提供电机状态和jtop提供的大多数信息
使用方法：
先激活env_unitree虚拟环境
新开terminal
运行python3 /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/main_dog_status.py（接受信息并整合发布）
新开terminal
运行python3 /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/for_Flask/app.py（接受整合后的信息并对接网页）
打开浏览器网页 http://127.0.0.1:5000

## 功能：控制狗头
功能描述：控制狗头转动到指定角度并作出指定表情
使用方法：
先激活env_unitree虚拟环境
新开terminal
运行python3 /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/main_dog_head_control.py
备注：新增了头部双维度摆动限位。表情：l向左看，r向右看，c向前看，h开心表情