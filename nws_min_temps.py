"""
nws_min_temps.py

    - Fetches NWS hourly temp data for next n hours, calculates min and max temps
    - If any temps go under freezing, notes the timestamp that they start
    - If temps that have gone under freezing come back above it within the window, notes the timestamp they end

"""
import datetime
import json
import os
import pathlib

from dotenv import load_dotenv
import requests


ROOT = pathlib.Path(__file__).parent
load_dotenv(dotenv_path=ROOT.joinpath('.env'))

def convert_to_c(temp_f: float) -> float:
    return (temp_f - 32) * (5/9)

def gather_data():
    NEXT_N_HOURS = 18
    hass_domain = os.environ['HASS_DOMAIN']
    hass_token = os.environ['HASS_TOKEN']
    nws_station = os.environ['NWS_STATION_ID']
    nws_points = os.environ['NWS_POINTS']

    resp = requests.get(f"https://api.weather.gov/gridpoints/{nws_station}/{nws_points}/forecast/hourly")
    resp.raise_for_status()

    data = resp.json()
    # Get the hourly forecasts
    periods = data['properties']['periods']

    temps = []
    freezing_temps_start_timestamp = freezing_temps_end_timestamp = freezing_temps_duration = None

    for i, period in enumerate(periods[:NEXT_N_HOURS]):
        temp_c = convert_to_c(period['temperature'])
        temps.append(temp_c)
        if freezing_temps_start_timestamp is None and temp_c < 0:
            # Capture only first hour of below-zero temps
            freezing_temps_start_timestamp = period['startTime']
        if freezing_temps_start_timestamp is not None and freezing_temps_end_timestamp is None and temp_c > 0:
            freezing_temps_end_timestamp = period['endTime']
    if freezing_temps_start_timestamp is not None and freezing_temps_end_timestamp is not None:
        start = datetime.datetime.strptime(freezing_temps_start_timestamp, '%Y-%m-%dT%H:%M:%S%z')
        end = datetime.datetime.strptime(freezing_temps_end_timestamp, '%Y-%m-%dT%H:%M:%S%z')
        freezing_temps_duration = (end - start).total_seconds() / 60 / 60

    min_temp = min(temps)

    # Send data to HASS
    resp = requests.post(
        f'http://{hass_domain}/api/states/sensor.nws_upcoming_min_temp',
        headers={
            'Authorization': f'Bearer {hass_token}',
            'content-type': 'application/json'
        },
        data=json.dumps({
            'state': round(min_temp, 1),
            'attributes': {
                'unit_of_measurement': '°C',
                'friendly_name': 'NWS Upcoming Min Temp',
                'freezing_temp_starts': freezing_temps_start_timestamp,
                'freezing_temp_ends': freezing_temps_end_timestamp,
                'freezing_temp_duration': freezing_temps_duration
            }
        })
    )


if __name__ == '__main__':
    gather_data()