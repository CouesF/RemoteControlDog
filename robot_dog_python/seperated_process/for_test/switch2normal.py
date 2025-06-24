import time
import sys

# Core SDK components for communication
from unitree_sdk2py.core.channel import ChannelFactoryInitialize

# High-level control clients
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient # For Go2, Go2-W, B2, B2-W

class RobotModeControl:
    def __init__(self, robot_type="go2"):
        self.robot_type = robot_type
        self.msc = MotionSwitcherClient()
        self.sport_client = SportClient() if robot_type == "go2" else None

    def init_clients(self):
        """Initializes all necessary SDK clients."""
        self.msc.SetTimeout(5.0)
        self.msc.Init()

        if self.robot_type == "go2":
            self.sport_client.SetTimeout(5.0)
            self.sport_client.Init()

    def _release_current_mode(self):
        """Ensures no high-level mode is active."""
        print("Attempting to release current control mode...")
        status, result = self.msc.CheckMode()
        mode_released = False
        if status == 0 and result['name']: # Check status for successful call and if a mode is active
            print(f"Current mode: {result['name']}. Attempting to release...")
            while status == 0 and result['name']:
                self.msc.ReleaseMode()
                time.sleep(1) # Give the robot time to process
                status, result = self.msc.CheckMode()
            mode_released = True
            print("Current control mode released.")
        elif status != 0:
            print(f"Failed to check current mode, status code: {status}. Proceeding anyway.")
            mode_released = False # Indicate uncertainty, but allow proceeding
        else:
            print("No active mode found, proceeding.")
            mode_released = True
        return mode_released

    def switch_to_mode(self, mode_name: str):
        """
        Switches the robot to the specified high-level control mode.
        First, it attempts to release any currently active mode.
        Then, it selects the new mode and, for Go2, sends a StandUp command.
        """
        if not self._release_current_mode():
            print("Failed to release current mode or encountered an error checking mode. Proceeding with mode selection anyway.")
            # Depending on robustness needs, you might want to return False here
            # return False

        print(f"Attempting to switch to high-level control mode: '{mode_name}'...")
        if self.robot_type == "go2":
            ret = self.msc.SelectMode(mode_name)
            if ret == 0: # Assuming 0 for success
                print(f"High-level control mode '{mode_name}' activated successfully.")
                time.sleep(1) # Give robot time to switch mode
                # After selecting a mode like "normal" or "ai", typically the robot would stand up.
                # Sending StandUp command ensures the robot assumes a stable posture.
                self.sport_client.StandUp()
                print("Robot received StandUp command.")
                return True
            else:
                print(f"Failed to activate high-level control mode '{mode_name}'. Return code: {ret}")
                return False
        else:
            print(f"Robot type '{self.robot_type}' not supported for this mode switching logic.")
            return False

    def check_current_mode(self):
        """Checks and prints the current form and motion mode of the robot."""
        print("Checking current robot mode...")
        form = ""
        name = ""
        status, result = self.msc.CheckMode()
        if status == 0:
            form = result.get('form', 'N/A')
            name = result.get('name', 'N/A')
            print(f"Current Form: {form}, Current Mode: {name}")
            return form, name
        else:
            print(f"Failed to check current mode. Return code: {status}")
            return "Error", "Error"

if __name__ == '__main__':
    print("WARNING: Ensure the robot is on a safe, clear surface before running.")
    input("Press Enter to continue...")

    ChannelFactoryInitialize(0, "enP8p1s0")

    controller = RobotModeControl(robot_type="go2")
    controller.init_clients()

    time.sleep(2) # Allow some time for clients to initialize

    # Check initial mode
    print("\n--- Initial Mode Check ---")
    controller.check_current_mode()

    print("\n--- Phase: Switch to 'normal' mode ---")
    if controller.switch_to_mode(mode_name="ai"):
        print("Successfully requested switch to 'normal' mode and StandUp.")
        time.sleep(5) # Allow time for the robot to settle in the new mode and stand up
    else:
        print("Failed to switch to 'normal' mode.")

    # Check mode after switching
    print("\n--- Final Mode Check ---")
    controller.check_current_mode()

    print("\nScript complete.")
    sys.exit(0)