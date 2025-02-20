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
from typing import (
    Dict,
    Union
)

from dotenv import load_dotenv
import requests


ROOT = pathlib.Path(__file__).parent
load_dotenv(dotenv_path=ROOT.joinpath('.env'))

HASS_DOMAIN = os.environ['HASS_DOMAIN']
HASS_TOKEN = os.environ['HASS_TOKEN']
NWS_STATION = os.environ['NWS_STATION_ID']
NWS_POINTS = os.environ['NWS_POINTS']

def post_sensor(sensor_name: str, state: Union[str, float], attributes: Dict[str, Union[str, float]]):
    url = f'http://{HASS_DOMAIN}/api/states/sensor.{sensor_name}'
    requests.post(
        url,
        headers={
            'Authorization': f'Bearer {HASS_TOKEN}',
            'content-type': 'application/json'
        },
        data=json.dumps({
            'state': state,
            'attributes': attributes
        })
    )

def convert_to_c(temp_f: float) -> float:
    return (temp_f - 32) * (5/9)

def gather_data():
    NEXT_N_HOURS = 18


    resp = requests.get(f"https://api.weather.gov/gridpoints/{NWS_STATION}/{NWS_POINTS}/forecast/hourly")
    resp.raise_for_status()

    data = resp.json()
    # Get the hourly forecasts
    periods = data['properties']['periods']
    current_period = periods[0]

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

    # Send upcoming min temp
    post_sensor(
        'nws_upcoming_min_temp',
        round(min_temp, 1),
        attributes={
            'unit_of_measurement': '°C',
            'state_class': 'measurement',
            'friendly_name': 'NWS Upcoming Min Temp',
            'freezing_temp_starts': freezing_temps_start_timestamp,
            'freezing_temp_ends': freezing_temps_end_timestamp,
            'freezing_temp_duration': freezing_temps_duration
        }
    )

    # Send current weather detail
    post_sensor(
        'nws_current',
        round(convert_to_c(current_period['temperature']), 1),
        attributes={
            'unit_of_measurement': '°C',
            'state_class': 'measurement',
            'friendly_name': 'NWS Current Weather',
            'wind_speed_mph': round(float(current_period['windSpeed'].replace(' mph', '')), 1),
            'short_forecast': current_period['shortForecast'],
            'humidity': current_period['relativeHumidity']['value'],
            'dewpoint': round(current_period['dewpoint']['value'], 1),
            'precip_probability': round(current_period['probabilityOfPrecipitation']['value'])
        }
    )


if __name__ == '__main__':
    gather_data()