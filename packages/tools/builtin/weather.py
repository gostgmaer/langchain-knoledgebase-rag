# ============================================================
# core/tools/weather.py — Weather Tool
# ============================================================
# TODO: Define `get_weather(location)` tool function
# TODO: Call OpenWeatherMap API using WEATHER_API_KEY
# TODO: Parse and format the weather response
# TODO: Handle API errors and invalid locations
# ============================================================


from dataclasses import dataclass

from packages.config.loader import settings
from langchain.tools import tool
import httpx

from packages.logging.logger import get_logger

logger = get_logger(__name__)

client = httpx.AsyncClient(timeout=10)


# @dataclass
# class WeatherData:
#     city: str
#     temperature: float
#     description: str


# @dataclass
# class Context:
#     user_id: str
#     city: str


# @dataclass
# class ResponseFormat:
#     summary: str
#     temperature_celsius: float
#     temperature_fahrenheit: float
#     humidity: float


@tool(
    "get_weather",
    description="Get the current weather for a given location.",
    return_direct=False,
)
async def get_weather(city: str):
    """Get the current weather for a city."""

    # url = os.getenv("OPENWEATHER_BASE_URL")

    # if not os.getenv("OPENWEATHER_API_KEY"):
    #     return "Weather API key is missing."
    # key = os.getenv("OPENWEATHER_API_KEY")
    logger.debug("Weather tool executed for %s", city)

    # geocoding = await client.get(
    #     url + "/geo/1.0/direct",
    #     params={"q": city, "limit": 1, "appid": key},
    # )
    # if geocoding.status_code != 200:
    #     return f"City '{city}' not found."
    # geocoding_data = geocoding.json()
    # lat = geocoding_data[0]["lat"]
    # lon = geocoding_data[0]["lon"]
    # print(f"Geocoding data for {city}: {lat}, {lon}")
    try:
        response = await client.get(
            f"{settings.tools.weather_api_url}/data/2.5/weather",
            params={
                "q": city,
                "lang": "en",
                "appid": settings.tools.weather_api_key,
                "units": "metric",
            },
        )

        response.raise_for_status()
        data = response.json()
        logger.debug("Weather tool executed for %s", city)
        logger.debug(f"Weather data for {city}: {data}")
        data = {
            "success": True,
            "tool": "get_weather",
            "query": {
                "city": city,
            },
            "location": {
                "city": data["name"],
                "country": data["sys"]["country"],
                "coordinates": {
                    "latitude": data["coord"]["lat"],
                    "longitude": data["coord"]["lon"],
                },
                "timezone_offset": data["timezone"],
            },
            "weather": {
                "main": data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "icon": data["weather"][0]["icon"],
            },
            "temperature": {
                "current": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "minimum": data["main"]["temp_min"],
                "maximum": data["main"]["temp_max"],
                "unit": "°C",
            },
            "atmosphere": {
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "sea_level": data["main"].get("sea_level"),
                "ground_level": data["main"].get("grnd_level"),
                "visibility_km": round(data.get("visibility", 0) / 1000, 1),
                "cloud_cover": data.get("clouds", {}).get("all"),
            },
            "wind": {
                "speed": data["wind"]["speed"],
                "direction": data["wind"].get("deg"),
                "gust": data["wind"].get("gust"),
                "unit": "m/s",
            },
            "sun": {
                "sunrise": data["sys"]["sunrise"],
                "sunset": data["sys"]["sunset"],
            },
            "precipitation": {
                "rain_1h": data.get("rain", {}).get("1h"),
                "rain_3h": data.get("rain", {}).get("3h"),
                "snow_1h": data.get("snow", {}).get("1h"),
                "snow_3h": data.get("snow", {}).get("3h"),
            },
            "metadata": {
                "observation_time": data["dt"],
                "api": "OpenWeatherMap",
                "units": "metric",
            },
            "summary": (
                f"It is currently {data['weather'][0]['description']} in "
                f"{data['name']}, {data['sys']['country']}. "
                f"The temperature is {data['main']['temp']}°C "
                f"(feels like {data['main']['feels_like']}°C) "
                f"with {data['main']['humidity']}% humidity and "
                f"wind speed of {data['wind']['speed']} m/s."
            ),
        }
        print(data)
        return data

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"City '{city}' not found."

        return f"Weather service returned HTTP {e.response.status_code}."

    except httpx.RequestError as e:
        return f"Unable to reach the weather service: {e}"
    # return WeatherData(
    #     city=city,
    #     temperature=data["current_condition"][0]["temp_C"],
    #     description=data["current_condition"][0]["weatherDesc"][0]["value"],
    # )
