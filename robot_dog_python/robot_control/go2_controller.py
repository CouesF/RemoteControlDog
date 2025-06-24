# RemoteControlDog/robot_dog_python/robot_control/go2_controller.py
import logging
import time
from .robot_state import RobotState

# Attempt to import Unitree SDK
try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.go2.sport.sport_client import SportClient
    UNITREE_SDK_AVAILABLE = True
except ImportError:
    UNITREE_SDK_AVAILABLE = False
    SportClientError = Exception # Define for type hinting if SDK not found
    class SportClient: # Mock class if SDK not available
        def Init(self): pass
        def SetTimeout(self, t): pass
        def Damp(self): return 0
        def BalanceStand(self): return 0
        def StopMove(self): return 0
        def StandUp(self): return 0
        def StandDown(self): return 0
        def Move(self, vx, vy, vyaw): return 0
        def Sit(self): return 0
        def RiseSit(self): return 0
        # Add other methods as needed for mock, returning 0 for success

logger = logging.getLogger(__name__)

# You might want to make this configurable
UNITREE_NETWORK_INTERFACE = "enP8p1s0" # Example, ensure this is correct for your robot

class Go2Controller:
    def __init__(self, network_interface=UNITREE_NETWORK_INTERFACE, timeout_s=10.0):
        self.state = RobotState.OFFLINE
        self.sport_client = None
        self.network_interface = network_interface
        self.timeout_s = timeout_s
        self.is_initialized = False

        if not UNITREE_SDK_AVAILABLE:
            logger.error("Unitree SDK not found. Robot control will be mocked.")
            # Potentially initialize the mock sport_client here if needed for basic testing
            self.sport_client = SportClient() # Mock
            self.state = RobotState.ERROR # Or a specific MOCKED state
            return

        try:
            logger.info(f"Initializing Unitree ChannelFactory with interface: {self.network_interface}")
            ChannelFactoryInitialize(0, self.network_interface)
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(self.timeout_s)
            logger.info("Initializing SportClient...")
            self.state = RobotState.INITIALIZING
            self.sport_client.Init() # This can take a moment
            self.is_initialized = True
            # Initial action: go to damped state for safety
            self.damp()
            logger.info("SportClient initialized and robot damped.")
        except SportClientError as e:
            logger.error(f"Failed to initialize Unitree SportClient: {e}", exc_info=True)
            self.state = RobotState.ERROR
            self.sport_client = None # Ensure it's None if init failed
        except Exception as e:
            logger.error(f"An unexpected error occurred during Go2Controller initialization: {e}", exc_info=True)
            self.state = RobotState.ERROR
            self.sport_client = None


    def _call_sdk(self, action_func, *args, success_state=None, failure_state=RobotState.ERROR, allowed_states=None):
        if not self.is_initialized or not self.sport_client:
            logger.error(f"SportClient not initialized. Cannot perform action: {action_func.__name__}")
            self.state = RobotState.ERROR
            return False

        if allowed_states and self.state not in allowed_states:
            logger.warning(f"Action '{action_func.__name__}' not allowed in current state '{self.state.name}'. Allowed: {allowed_states}")
            return False

        try:
            logger.info(f"Executing SDK action: {action_func.__name__} with args: {args}")
            # The SDK calls are blocking. For some actions, we might want to set ACTION_IN_PROGRESS
            # For now, we assume they complete relatively quickly or manage their own state.
            ret = action_func(*args)
            if ret == 0: # Success
                logger.info(f"SDK action '{action_func.__name__}' successful.")
                if success_state:
                    self.state = success_state
                return True
            else:
                logger.error(f"SDK action '{action_func.__name__}' failed with code: {ret}")
                self.state = failure_state
                return False
        except SportClientError as e:
            logger.error(f"SportClientError during '{action_func.__name__}': {e}", exc_info=True)
            self.state = failure_state
            return False
        except Exception as e:
            logger.error(f"Unexpected error during '{action_func.__name__}': {e}", exc_info=True)
            self.state = failure_state
            return False

    def get_current_state(self):
        return self.state

    def damp(self):
        # Damp can be called from almost any state
        return self._call_sdk(self.sport_client.Damp, success_state=RobotState.DAMPED)

    def balance_stand(self):
        # Typically called from STANDING_LOCKED or after RiseSit or to stop movement
        allowed = [RobotState.STANDING_LOCKED, RobotState.SITTING, RobotState.MOVING, RobotState.DAMPED, RobotState.BALANCED_STANDING]
        return self._call_sdk(self.sport_client.BalanceStand, success_state=RobotState.BALANCED_STANDING, allowed_states=allowed)

    def stop_move(self):
        # Stops current movement and transitions to BALANCED_STANDING
        allowed = [RobotState.MOVING]
        if self._call_sdk(self.sport_client.StopMove, success_state=RobotState.BALANCED_STANDING, allowed_states=allowed):
            return self.balance_stand() # Ensure it's in balance stand
        return False

    def stand_up(self):
        # From DAMPED, LYING_DOWN_LOCKED, SITTING
        allowed = [RobotState.DAMPED, RobotState.LYING_DOWN_LOCKED, RobotState.SITTING, RobotState.BALANCED_STANDING]
        return self._call_sdk(self.sport_client.StandUp, success_state=RobotState.STANDING_LOCKED, allowed_states=allowed)

    def stand_down(self):
        # From BALANCED_STANDING or STANDING_LOCKED
        allowed = [RobotState.BALANCED_STANDING, RobotState.STANDING_LOCKED]
        return self._call_sdk(self.sport_client.StandDown, success_state=RobotState.LYING_DOWN_LOCKED, allowed_states=allowed)

    def move(self, vx, vy, vyaw):
        if self.state != RobotState.BALANCED_STANDING and self.state != RobotState.MOVING:
            logger.warning(f"Move command received but robot not in BALANCED_STANDING or MOVING state. Current state: {self.state.name}. Attempting to go to BalanceStand first.")
            if not self.balance_stand():
                logger.error("Failed to transition to BalanceStand before moving.")
                return False
            time.sleep(1) # Give it a moment to stabilize in balance stand

        # If vx, vy, vyaw are all zero, it's a stop command
        if abs(vx) < 0.01 and abs(vy) < 0.01 and abs(vyaw) < 0.01 and self.state == RobotState.MOVING:
            logger.info("Move command with zero velocities, stopping movement.")
            return self.stop_move()

        # Only proceed if non-zero velocities or transitioning to move
        if abs(vx) >= 0.01 or abs(vy) >= 0.01 or abs(vyaw) >= 0.01:
            logger.info(f"Executing Move: vx={vx}, vy={vy}, vyaw={vyaw}")
            # The SDK Move command doesn't have a clear "success_state" change unless it was previously not MOVING.
            # It continuously applies velocity.
            current_moving_state = self.state == RobotState.MOVING
            if self._call_sdk(self.sport_client.Move, vx, vy, vyaw, success_state=RobotState.MOVING, allowed_states=[RobotState.BALANCED_STANDING, RobotState.MOVING]):
                if not current_moving_state: # If we just started moving
                    self.state = RobotState.MOVING
                return True
            return False
        return True # No actual movement command sent if all velocities are zero and not already moving

    def sit(self):
        allowed = [RobotState.BALANCED_STANDING, RobotState.STANDING_LOCKED]
        return self._call_sdk(self.sport_client.Sit, success_state=RobotState.SITTING, allowed_states=allowed)

    def rise_sit(self):
        allowed = [RobotState.SITTING]
        if self._call_sdk(self.sport_client.RiseSit, success_state=RobotState.BALANCED_STANDING, allowed_states=allowed):
            # After rising from sit, it goes to balance stand
            return self.balance_stand()
        return False

    def emergency_stop(self):
        logger.critical("Executing EMERGENCY STOP (DAMP)")
        return self.damp()

    def shutdown_sequence(self):
        logger.info("Initiating robot shutdown sequence...")
        if self.state not in [RobotState.DAMPED, RobotState.LYING_DOWN_LOCKED, RobotState.OFFLINE, RobotState.ERROR]:
            if self.state == RobotState.MOVING:
                self.stop_move()
                time.sleep(0.5) # Allow stopping
            if self.state != RobotState.SITTING and self.state != RobotState.LYING_DOWN_LOCKED:
                 # Prefer to stand up fully before lying down if not already in a low state
                if self.state != RobotState.STANDING_LOCKED and self.state != RobotState.BALANCED_STANDING:
                    logger.info("Standing up before lying down...")
                    self.stand_up()
                    time.sleep(2) # Allow time to stand

            if self.state != RobotState.LYING_DOWN_LOCKED:
                logger.info("Lying down...")
                self.stand_down()
                time.sleep(3) # Allow time to lie down
        
        logger.info("Damping motors for final shutdown.")
        self.damp()
        logger.info("Robot shutdown sequence complete.")
        # Note: SportClient itself doesn't have a 'close' or 'disconnect' method in the provided examples.
        # ChannelFactory cleanup might be implicit or handled at a lower SDK level.

    def raise_leg(self):
        print("Executing raise leg...")

        cmd = self._create_default_lowcmd()

        # Lift front-right leg (motors 0–2)
        cmd.motor_cmd[0].q = -0.3  # stretch leg forward
        cmd.motor_cmd[1].q = 0.3   # lift thigh
        cmd.motor_cmd[2].q = -0.3  # fold calf

        for i in range(12):
            cmd.motor_cmd[i].mode = 0x01  # position mode
            cmd.motor_cmd[i].kp = 60.0
            cmd.motor_cmd[i].kd = 5.0
            cmd.motor_cmd[i].tau = 0.0

        # Send command
        self.lowcmd_pub.Write(cmd)
        print("Right front leg lifted.")

