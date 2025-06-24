# RemoteControlDog/robot_dog_python/main_robot_dog.py
import sys
import os

# This is crucial for making relative imports work when running this script directly
# It adds the 'RemoteControlDog' directory to sys.path if robot_dog_python is inside it.
# Adjust if your execution context or structure is different.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # robot_dog_python
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..')) # RemoteControlDog

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if CURRENT_DIR not in sys.path: # To find sibling packages like 'app', 'robot_control'
    sys.path.insert(0, CURRENT_DIR)


# Now that paths are set, we can use absolute imports from the project root perspective
# or relative imports from within the robot_dog_python package.
# For consistency within the robot_dog_python package, we'll use relative style imports
# in the modules themselves (e.g., from . import config).
# Here, to import RobotDogClientApp which is in a sub-package 'app':
from robot_dog_python.app.robot_dog_client_app import RobotDogClientApp

def main():
    # Before anything, ensure protobuf definitions are generated and accessible
    # You might have a check here or rely on your generate_protos.sh script
    # For example:
    # proto_py_path = os.path.join(CURRENT_DIR, "communication", "protobuf_definitions", "messages_pb2.py")
    # if not os.path.exists(proto_py_path):
    #     print(f"Error: Protobuf definitions not found at {proto_py_path}")
    #     print("Please run your generation script (e.g., generate_protos.sh) first.")
    #     sys.exit(1)
        
    app = RobotDogClientApp()
    app.run()

if __name__ == "__main__":
    main()