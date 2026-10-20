#!/usr/bin/env python3
"""Simple CLI weather app using the Open-Meteo public API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IP_GEO_URL = "https://ipapi.co/json/"


# Mapping from Open-Meteo weather codes to human-readable descriptions.
WEATHER_CODE_DESCRIPTIONS: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class GeocodeResult:
    name: str
    country: str
    latitude: float
    longitude: float

    @property
    def display_name(self) -> str:
        if self.country:
            return f"{self.name}, {self.country}"
        return self.name


def fetch_json(url: str, params: Dict[str, str]) -> Dict:
    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}" if params else url
    request = urllib.request.Request(request_url, headers={"User-Agent": "simple-weather-app/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status code {response.status} for {request_url}")
        try:
            return json.load(response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse JSON from {request_url}") from exc


def geocode_location(name: str) -> GeocodeResult:
    data = fetch_json(
        GEOCODE_URL,
        {
            "name": name,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )
    results = data.get("results")
    if not results:
        raise ValueError(f"Could not find location named '{name}'.")

    result = results[0]
    return GeocodeResult(
        name=result.get("name", name),
        country=result.get("country", ""),
        latitude=float(result["latitude"]),
        longitude=float(result["longitude"]),
    )


def ip_location() -> GeocodeResult:
    data = fetch_json(IP_GEO_URL, {})
    city = data.get("city")
    country = data.get("country_name") or data.get("country") or ""
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if not city or latitude is None or longitude is None:
        raise RuntimeError("Could not determine location from IP address.")
    return GeocodeResult(
        name=city,
        country=country,
        latitude=float(latitude),
        longitude=float(longitude),
    )


def fetch_current_weather(
    latitude: float,
    longitude: float,
    unit: str,
) -> Tuple[float, int]:
    data = fetch_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "temperature_unit": unit,
        },
    )
    current = data.get("current_weather")
    if not current:
        raise RuntimeError("API response missing current weather data.")

    temperature = float(current["temperature"])
    weather_code = int(current["weathercode"])
    return temperature, weather_code


def describe_weather_code(code: int) -> str:
    return WEATHER_CODE_DESCRIPTIONS.get(code, f"Unknown weather code ({code})")


def parse_args(argv: Optional[Tuple[str, ...]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch current weather for a city using the Open-Meteo API.",
    )
    parser.add_argument(
        "location",
        nargs="?",
        help="City name to look up (e.g. 'London'). If omitted, the app uses your IP-based location.",
    )
    parser.add_argument(
        "--fahrenheit",
        action="store_true",
        help="Display temperature in Fahrenheit instead of Celsius.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Tuple[str, ...]] = None) -> int:
    args = parse_args(argv)

    try:
        location = geocode_location(args.location) if args.location else ip_location()
        unit = "fahrenheit" if args.fahrenheit else "celsius"
        temperature, weather_code = fetch_current_weather(location.latitude, location.longitude, unit)
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        print(f"Network error: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # pylint: disable=broad-except
        print(f"Error: {error}", file=sys.stderr)
        return 1

    unit_symbol = "°F" if args.fahrenheit else "°C"
    description = describe_weather_code(weather_code)

    print(location.display_name)
    print(f"{temperature:.1f}{unit_symbol} — {description}")
    return 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
