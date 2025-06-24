# main_dog_status.py (Final Confirmed Version)

import time
import sys
import os
import json
import datetime

# Debug flag is now permanently False
DEBUG_JTOP = False
DDS_NETWORK_INTERFACE = "enP8p1s0"
# --- FIX FOR CROSS-DIRECTORY IMPORT ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
# --- END OF FIX ---

from dds_data_structure import DogStatus, JetsonTemperatures, JetsonPower, JetsonHardware
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from jtop import jtop, JtopException

def json_default_serializer(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    if isinstance(o, datetime.timedelta):
        return o.total_seconds()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def get_jtop_val(stat_obj):
    """Safely extracts a value from a jtop statistic."""
    if isinstance(stat_obj, (int, float)):
        return float(stat_obj)
    if isinstance(stat_obj, dict):
        return float(stat_obj.get('val', 0.0))
    return 0.0

def populate_jetson_details(dog_status_msg, stats):
    """
    Populates detailed Jetson stats using the confirmed keys from your debug output.
    """
    dog_status_msg.temperatures.cpu = stats.get('Temp tj', 0.0)
    dog_status_msg.temperatures.gpu = stats.get('Temp gpu', 0.0)
    dog_status_msg.temperatures.soc0 = stats.get('Temp soc0', 0.0)
    dog_status_msg.temperatures.soc1 = stats.get('Temp soc1', 0.0)
    dog_status_msg.temperatures.soc2 = stats.get('Temp soc2', 0.0)
    dog_status_msg.temperatures.cv0 = stats.get('Temp cv0', 0.0)
    dog_status_msg.temperatures.cv1 = stats.get('Temp cv1', 0.0)
    dog_status_msg.temperatures.cv2 = stats.get('Temp cv2', 0.0)
    dog_status_msg.temperatures.tj = stats.get('Temp cpu', 0.0)

    dog_status_msg.power.cpu_gpu_cv = stats.get('Power VDD_CPU_GPU_CV', 0)
    dog_status_msg.power.soc = stats.get('Power VDD_SOC', 0)
    # --- FINAL FIX: Map 'Power TOT' to the VDD_INN field ---
    dog_status_msg.power.vdd_inn = stats.get('Power TOT', 0)
    dog_status_msg.power.nv_power_total = stats.get('Power TOT', 0)

    # Note: 'disk' key is not provided by the jtop python library, so it will correctly be 0.
    disk_stats = stats.get('disk', {})
    disk_used = disk_stats.get('used', 0)
    disk_total = disk_stats.get('total', 0)
    dog_status_msg.hardware.disk_usage_percent = (disk_used / disk_total) * 100 if disk_total > 0 else 0
    
    dog_status_msg.hardware.emc_usage_percent = get_jtop_val(stats.get('EMC'))
    dog_status_msg.hardware.fan_speed_percent = get_jtop_val(stats.get('Fan pwmfan0'))
    
    uptime_val = stats.get('uptime')
    if isinstance(uptime_val, datetime.timedelta):
        dog_status_msg.hardware.uptime_seconds = int(uptime_val.total_seconds())
    else:
        dog_status_msg.hardware.uptime_seconds = int(uptime_val or 0)
    
    dog_status_msg.hardware.jetson_clocks_on = True if stats.get('jetson_clocks', 'OFF') == 'ON' else False

def main():
    global DEBUG_JTOP, DDS_NETWORK_INTERFACE
    DDS_NETWORK_INTERFACE = "enP8p1s0"
    msc, lowstate_sub, dog_status_pub = None, None, None

    try:
        with jtop() as jetson:
            if not jetson.ok():
                print("Failed to connect to the jtop service.")
                return

            print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}")
            ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
            
            lowstate_sub = ChannelSubscriber("rt/lowstate", LowState_)
            lowstate_sub.Init()
            dog_status_pub = ChannelPublisher("DogStatus", DogStatus)
            dog_status_pub.Init()
            msc = MotionSwitcherClient()
            msc.SetTimeout(5.0)
            msc.Init()

            print("Successfully connected to services. Starting unified monitoring...")
            print("Press Ctrl+C to stop.")

            while jetson.ok():
                stats = jetson.stats

                if DEBUG_JTOP:
                    print("\n--- JTOP DEBUG OUTPUT (WILL PRINT ONCE) ---")
                    print(json.dumps(stats, indent=4, default=json_default_serializer))
                    print("--- END OF JTOP DEBUG OUTPUT ---\n")
                    DEBUG_JTOP = False

                lowstate_msg = lowstate_sub.Read(200)

                if lowstate_msg is not None:
                    dog_status_to_publish = DogStatus()
                    
                    cpu_cores = [k for k in stats if k.startswith('CPU') and k[3:].isdigit()]
                    total_cpu_usage = sum(get_jtop_val(stats.get(core)) for core in cpu_cores)
                    dog_status_to_publish.cpu_usage_percent = total_cpu_usage / len(cpu_cores) if cpu_cores else 0.0

                    dog_status_to_publish.timestamp_ns = time.time_ns()
                    dog_status_to_publish.battery_percent = float(lowstate_msg.bms_state.soc)
                    dog_status_to_publish.gpu_usage_percent = get_jtop_val(stats.get('GPU'))
                    dog_status_to_publish.memory_usage_percent = get_jtop_val(stats.get('RAM')) * 100.0
                    
                    status, result = msc.CheckMode()
                    if status == 0:
                        dog_status_to_publish.robot_mode_form = result.get('form', 'N/A')
                        dog_status_to_publish.robot_mode_name = result.get('name', 'N/A')
                    else:
                        dog_status_to_publish.robot_mode_name = "Error"
                    
                    populate_jetson_details(dog_status_to_publish, stats)

                     # --- EXPANDED: Populate all 9 fields for all 12 motors ---
                    for i in range(12):
                        motor = lowstate_msg.motor_state[i]
                        setattr(dog_status_to_publish, f'm{i}_mode', motor.mode)
                        setattr(dog_status_to_publish, f'm{i}_q', motor.q)
                        setattr(dog_status_to_publish, f'm{i}_dq', motor.dq)
                        setattr(dog_status_to_publish, f'm{i}_ddq', motor.ddq)
                        setattr(dog_status_to_publish, f'm{i}_tau_est', motor.tau_est)
                        setattr(dog_status_to_publish, f'm{i}_temperature', motor.temperature)
                        setattr(dog_status_to_publish, f'm{i}_lost', motor.lost)
                        # The 'reserve' field in the SDK is an array
                        setattr(dog_status_to_publish, f'm{i}_reserve0', motor.reserve[0])
                        setattr(dog_status_to_publish, f'm{i}_reserve1', motor.reserve[1])
                    # --- END OF UPDATE ---

                    dog_status_pub.Write(dog_status_to_publish)

                    print(f"Published: "
                          f"Mode='{dog_status_to_publish.robot_mode_name}' | "
                          f"SoC={dog_status_to_publish.battery_percent:.1f}% | "
                          f"CPU={dog_status_to_publish.cpu_usage_percent:.1f}% | "
                          f"GPU={dog_status_to_publish.gpu_usage_percent:.1f}% | "
                          f"CPU Temp={dog_status_to_publish.temperatures.cpu:.1f}°C")
                else:
                    pass
                
                time.sleep(0.8)

    except JtopException as e:
        print(f"An error occurred with jtop: {e}")
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        print("\nShutdown complete.")
        if lowstate_sub: lowstate_sub.Close()
        if dog_status_pub: dog_status_pub.Close()

if __name__ == "__main__":
    main()