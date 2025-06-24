import serial

try:
    ser = serial.Serial(
        port='/dev/ttyTHS1', # Failed. So which port should i look at
        baudrate=115200,
        bytesize=8,      # Using integer 8 directly
        parity='N',      # Using character 'N' directly
        stopbits=1,      # Using integer 1 directly
        timeout=1
    )
    print("Serial port opened successfully!")
    # Your serial communication logic here
    ser.close()

except serial.SerialException as e:
    print(f"Serial port error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")