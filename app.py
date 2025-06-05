from flask import Flask, render_template, jsonify, request
from skyfield.api import load, EarthSatellite, wgs84
import json
import time
import serial
import serial.tools.list_ports
from datetime import datetime

app = Flask(__name__)

# Serial port configuration
SERIAL_PORT = None  # Will be set via frontend
BAUD_RATE = 9600
ser = None

# Load satellite data
with open('satellites.json', 'r') as f:
    SATELLITE_DATA = json.load(f)

# Ground station coordinates (Lucknow, India)
LUCKNOW_LAT = 26.8467
LUCKNOW_LON = 80.9462
LUCKNOW_ELEV_M = 120

# Skyfield setup
ts = load.timescale()
lucknow_observer = wgs84.latlon(LUCKNOW_LAT, LUCKNOW_LON, elevation_m=LUCKNOW_ELEV_M)

def get_satellite_position(satellite):
    """Calculate satellite position"""
    t = ts.now()
    geocentric = satellite.at(t)
    difference = satellite - lucknow_observer
    topocentric = difference.at(t)
    alt, az, distance = topocentric.altaz()
    
    if alt.degrees < 0:
        return None, None
    return az.degrees, alt.degrees

def send_to_arduino(azimuth, elevation):
    """Send azimuth and elevation data to Arduino in the required format"""
    if ser is None or not ser.is_open:
        return False
        
    az_str = f"AZ{int(round(azimuth))}"
    el_str = f"EL{int(round(elevation))}"
    command = f"<{az_str}><{el_str}>\n"
    
    try:
        ser.write(command.encode('utf-8'))
        return True
    except serial.SerialException as e:
        print(f"Error writing to serial port: {e}")
        return False

def initialize_serial(port):
    """Initialize serial connection with the given port"""
    global ser
    try:
        if ser and ser.is_open:
            ser.close()
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)  # Give Arduino time to reset
        return True
    except serial.SerialException as e:
        print(f"Could not open serial port {port}: {e}")
        return False

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', satellites=SATELLITE_DATA['satellites'])

@app.route('/get_serial_ports', methods=['GET'])
def get_serial_ports():
    """Get list of available serial ports"""
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return jsonify({'ports': ports})

@app.route('/set_serial_port', methods=['POST'])
def set_serial_port():
    """Set the serial port for Arduino communication"""
    port = request.json.get('port')
    if not port:
        return jsonify({'error': 'No port specified'}), 400
    
    if initialize_serial(port):
        return jsonify({'message': f'Successfully connected to {port}'})
    else:
        return jsonify({'error': f'Failed to connect to {port}'}), 500

@app.route('/get_satellite_data', methods=['POST'])
def get_satellite_data():
    """Get real-time satellite data"""
    satellite_name = request.json.get('satellite_name')
    
    # Find selected satellite data
    satellite_info = next((sat for sat in SATELLITE_DATA['satellites'] 
                          if sat['name'] == satellite_name), None)
    
    if not satellite_info:
        return jsonify({'error': 'Satellite not found'}), 404
    
    # Create satellite object
    satellite = EarthSatellite(
        satellite_info['tle_line1'],
        satellite_info['tle_line2'],
        satellite_info['name'],
        ts
    )
    
    # Get position
    az, el = get_satellite_position(satellite)
    
    if az is None or el is None:
        return jsonify({
            'error': 'Satellite is below horizon',
            'timestamp': datetime.now().strftime('%H:%M:%S UTC')
        })
    
    # Send data to Arduino if serial connection is available
    serial_status = "disconnected"
    if ser and ser.is_open:
        if send_to_arduino(az, el):
            serial_status = "connected"
    
    return jsonify({
        'azimuth': round(az, 2),
        'elevation': round(el, 2),
        'timestamp': datetime.now().strftime('%H:%M:%S UTC'),
        'serial_status': serial_status
    })

@app.route('/set_manual_position', methods=['POST'])
def set_manual_position():
    """Set manual position for the antenna"""
    data = request.json
    azimuth = data.get('azimuth')
    elevation = data.get('elevation')
    
    if azimuth is None or elevation is None:
        return jsonify({'error': 'Missing azimuth or elevation values'}), 400
    
    if not (0 <= azimuth <= 360):
        return jsonify({'error': 'Azimuth must be between 0 and 360 degrees'}), 400
    
    if not (0 <= elevation <= 90):
        return jsonify({'error': 'Elevation must be between 0 and 90 degrees'}), 400
    
    if ser and ser.is_open:
        if send_to_arduino(azimuth, elevation):
            return jsonify({
                'message': 'Position updated successfully',
                'azimuth': round(azimuth, 2),
                'elevation': round(elevation, 2),
                'timestamp': datetime.now().strftime('%H:%M:%S UTC')
            })
        else:
            return jsonify({'error': 'Failed to send position to Arduino'}), 500
    else:
        return jsonify({'error': 'Serial port not connected'}), 400

if __name__ == '__main__':
    app.run(debug=True) 