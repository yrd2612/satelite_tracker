from skyfield.api import load, EarthSatellite, wgs84
import serial
import time
import datetime

# --- Configuration ---
# Replace with your Arduino's serial port.
# On Windows, it might be 'COM3', 'COM4', etc.
# On Linux/macOS, it might be '/dev/ttyUSB0', '/dev/ttyACM0', '/dev/cu.usbmodemXXXX', etc.
SERIAL_PORT = 'COM3'  # <--- IMPORTANT: CHANGE THIS TO YOUR ARDUINO'S SERIAL PORT
BAUD_RATE = 9600

# Your ground station coordinates (Lucknow, India)
# Latitude: 26.8467° N
# Longitude: 80.9462° E
# Elevation: Approx 120 meters above sea level
LUCKNOW_LAT = 26.8467
LUCKNOW_LON = 80.9462
LUCKNOW_ELEV_M = 120

# Satellite TLE (Two-Line Element Set) - Example: International Space Station (ISS)
# You should update this regularly from a source like Celestrak.com
# Search for 'ISS' on Celestrak and copy the "Current TLE"
SAT_NAME = 'ISS (ZARYA)'
TLE_LINE1 = '1 25544U 98067A   24155.85623091  .00003058  00000-0  60913-4 0  9997'
TLE_LINE2 = '2 25544  51.6416 116.5866 0005703  97.0345  36.5701 15.49845326451631'

# Update interval in seconds (how often to send data to Arduino)
UPDATE_INTERVAL_SECONDS = 2 # Adjust as needed, be careful not to overwhelm Arduino

# --- Skyfield Setup ---
ts = load.timescale()
planets = load('de421.bsp') # High-precision planet data, useful if you need to account for them
satellite = EarthSatellite(TLE_LINE1, TLE_LINE2, SAT_NAME, ts)

# Define your ground station
lucknow_observer = wgs84.latlon(LUCKNOW_LAT, LUCKNOW_LON, elevation_m=LUCKNOW_ELEV_M)

def get_satellite_position():
    """
    Calculates the current azimuth and elevation of the satellite from the ground station.
    Returns:
        tuple: (azimuth_degrees, elevation_degrees) or (None, None) if below horizon.
    """
    t = ts.now()
    geocentric = satellite.at(t)
    difference = satellite - lucknow_observer
    topocentric = difference.at(t)

    alt, az, distance = topocentric.altaz()

    if alt.degrees < 0:
        return None, None # Satellite is below the horizon
    else:
        return az.degrees, alt.degrees

def send_to_arduino(ser, azimuth, elevation):
    """
    Sends azimuth and elevation data to Arduino in the required format.
    Args:
        ser (serial.Serial): The serial port object.
        azimuth (float): Azimuth in degrees.
        elevation (float): Elevation in degrees.
    """
    # Format to <AZxxx><ELxxx>
    # Note: Your Arduino code expects integers, so we'll round and cast.
    # It also seems to handle negative elevation by setting it to 0,
    # but we'll ensure we only send positive if calculated is >=0.
    # The Arduino code specifically checks for 'EL-' and sets ComElev to 0.
    # If the calculated elevation is negative, we should probably set ComElev to 0
    # or not send the command at all for elevation. For this script, we return None if below horizon.

    # Arduino expects integer degrees.
    # The Arduino code handles ComAzim % 360, and ComElev for 0-180 range.
    # We will send positive degrees directly.
    az_str = f"AZ{int(round(azimuth))}"
    el_str = f"EL{int(round(elevation))}"

    command = f"<{az_str}><{el_str}>\n" # Add newline for readString() to terminate
    # print(f"Sending: {command.strip()}") # For debugging
    try:
        ser.write(command.encode('utf-8'))
        # You can add a small delay here if the Arduino struggles with rapid writes
        # time.sleep(0.01)
    except serial.SerialException as e:
        print(f"Error writing to serial port: {e}")
        return False
    return True


# --- Main Loop ---
if __name__ == "__main__":
    try:
        # Establish serial connection
        print(f"Attempting to open serial port: {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) # Timeout for read operations
        time.sleep(2) # Give Arduino time to reset after serial connection
        print("Serial port opened successfully.")

        print(f"Starting satellite tracking for: {SAT_NAME}")
        print(f"Ground station: Lat={LUCKNOW_LAT}, Lon={LUCKNOW_LON}, Elev={LUCKNOW_ELEV_M}m")
        print("Waiting for satellite data...")

        while True:
            az, el = get_satellite_position()

            if az is not None and el is not None:
                # print(f"Calculated: Azimuth={az:.2f}°, Elevation={el:.2f}°")
                if send_to_arduino(ser, az, el):
                    print(f"Sent: AZ{int(round(az))} EL{int(round(el))}")
                else:
                    print("Failed to send data to Arduino. Exiting.")
                    break
            else:
                print(f"Satellite {SAT_NAME} is below the horizon at {datetime.datetime.now().strftime('%H:%M:%S UTC')}. No data sent.")

            time.sleep(UPDATE_INTERVAL_SECONDS)

    except serial.SerialException as e:
        print(f"Could not open serial port {SERIAL_PORT}: {e}")
        print("Please check if the Arduino is connected and the correct port is selected.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            print("Closing serial port.")
            ser.close()