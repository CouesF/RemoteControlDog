import time
import sys
import os

# Add the parent directory to sys.path to import robot_control
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from robot_control.go2_controller import Go2Controller

def main():
    print("Initializing robot controller...")
    dog = Go2Controller()

    print("Standing up...")
    if not dog.stand_up():
        print("Failed to stand up. Exiting.")
        return
    print("Successfully stood up.")
    time.sleep(2)

    print("Switching to balance stand mode...")
    dog.balance_stand()
    time.sleep(2)

    print("Executing raise leg action...")
    dog.raise_leg()
    time.sleep(3)

    print("Returning to balance stand mode...")
    dog.balance_stand()
    time.sleep(2)

    print("Lying down...")
    if dog.stand_down():
        print("Successfully lay down.")
    else:
        print("Failed to lie down.")

    print("Motion test completed.")

if __name__ == "__main__":
    main()
