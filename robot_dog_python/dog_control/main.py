import time
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from robot_control.go2_controller import Go2Controller

def main():
    print("Initializing robot controller...")
    dog = Go2Controller()

    print("Trying to stand up...")
    if dog.stand_up():
        print("Successfully stood up.")
    else:
        print("Failed to stand up.")
        return

    time.sleep(1)

    print("Switching to balance stand mode...")
    dog.balance_stand()
    time.sleep(2)

    print("Walking forward...")
    dog.move(0.2, 0.0, 0.0)
    time.sleep(2)

    print("Stopping movement...")
    dog.stop_move()
    time.sleep(1)

    print("Re-entering balance stand before standing down...")
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
