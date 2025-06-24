# RemoteControlDog/robot_dog_python/robot_control/robot_state.py
from enum import Enum, auto

class RobotState(Enum):
    OFFLINE = auto()            # SDK not initialized or communication lost
    INITIALIZING = auto()       # SDK initializing
    DAMPED = auto()             # Motors are damped (emergency stop or safe mode)
    STANDING_LOCKED = auto()    # Robot is standing, joints locked (after StandUp)
    LYING_DOWN_LOCKED = auto()  # Robot is lying down, joints locked (after StandDown)
    BALANCED_STANDING = auto()  # Robot is in balance stand mode, ready for movement/posture changes
    MOVING = auto()             # Robot is actively moving (velocity commands)
    SITTING = auto()            # Robot is sitting
    RECOVERY = auto()           # Robot is recovering (e.g., from fall)
    ACTION_IN_PROGRESS = auto() # A specific SDK action (like Hello, Dance) is running
    ERROR = auto()              # An error occurred in the controller