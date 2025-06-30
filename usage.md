# start Woz system
cd /home/d3lab/Projects/RemoteControlDog/robot_dog_python && /home/d3lab/Projects/RemoteControlDog/robot_dog_python/env_unitree/bin/python start_woz_backend.py

# Start cam gateway
cd /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process && /home/d3lab/Projects/RemoteControlDog/robot_dog_python/env_unitree/bin/python main_camera_gateway.py

cd /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process && /home/d3lab/Projects/RemoteControlDog/robot_dog_python/env_unitree/bin/python main_control_gateway.py