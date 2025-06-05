from flask import Flask, render_template, jsonify, request
from skyfield.api import load, EarthSatellite, wgs84
import json
import time
from datetime import datetime

app = Flask(__name__)

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

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', satellites=SATELLITE_DATA['satellites'])

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
    
    return jsonify({
        'azimuth': round(az, 2),
        'elevation': round(el, 2),
        'timestamp': datetime.now().strftime('%H:%M:%S UTC')
    })

if __name__ == '__main__':
    app.run(debug=True) 