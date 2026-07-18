# ============================================================
# core/tools/weather.py — Weather Tool
# ============================================================
# TODO: Define `get_weather(location)` tool function
# TODO: Call OpenWeatherMap API using WEATHER_API_KEY
# TODO: Parse and format the weather response
# TODO: Handle API errors and invalid locations
# ============================================================


from dataclasses import dataclass

from langchain.tools import tool
import httpx

from config.settings import settings
from shared.logger import logger

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

    if not settings.weather_api_key:
        return "Weather API key is missing."
    logger.debug("Weather tool executed for %s", city)
    try:
        response = await client.get(
            settings.weather_api_url,
            params={
                "q": city,
                "appid": settings.weather_api_key,
                "units": "metric",
            },
        )

        response.raise_for_status()
        data = response.json()
        logger.debug("Weather tool executed for %s", city)
        logger.debug(f"Weather data for {city}: {data}")
        return (
            f"📍 {data['name']}, {data['sys']['country']}\n"
            f"🌤 {data['weather'][0]['description'].title()}\n"
            f"🌡 {data['main']['temp']}°C\n"
            f"🤗 Feels Like: {data['main']['feels_like']}°C\n"
            f"💧 Humidity: {data['main']['humidity']}%\n"
            f"💨 Wind: {data['wind']['speed']} m/s"
        )

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
