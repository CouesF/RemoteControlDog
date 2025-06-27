import os

def shutdown_jetson():
    """
    Shuts down the Jetson board.
    Requires superuser privileges to execute.
    """
    try:
        print("Attempting to shut down the Jetson board...")
        os.system("sudo shutdown -h now")
        print("Shutdown command issued. The system should power off shortly.")
    except Exception as e:
        print(f"An error occurred during shutdown: {e}")
        print("Please ensure you have the necessary permissions (e.g., by running with sudo).")

def reboot_jetson():
    """
    Reboots the Jetson board.
    Requires superuser privileges to execute.
    """
    try:
        print("Attempting to reboot the Jetson board...")
        os.system("sudo reboot")
        print("Reboot command issued. The system should restart shortly.")
    except Exception as e:
        print(f"An error occurred during reboot: {e}")
        print("Please ensure you have the necessary permissions (e.g., by running with sudo).")

if __name__ == "__main__":
    print("Jetson Power Management Script")
    print("----------------------------")
    print("WARNING: These commands will power off or restart your system.")
    print("Ensure all your work is saved before proceeding.")

    while True:
        choice = input("\nEnter 's' for shutdown, 'r' for reboot, or 'q' to quit: ").lower()
        if choice == 's':
            confirm = input("Are you sure you want to shut down? (yes/no): ").lower()
            if confirm == 'yes':
                shutdown_jetson()
                break # Exit after issuing command
            else:
                print("Shutdown cancelled.")
        elif choice == 'r':
            confirm = input("Are you sure you want to reboot? (yes/no): ").lower()
            if confirm == 'yes':
                reboot_jetson()
                break # Exit after issuing command
            else:
                print("Reboot cancelled.")
        elif choice == 'q':
            print("Exiting script.")
            break
        else:
            print("Invalid choice. Please enter 's', 'r', or 'q'.")