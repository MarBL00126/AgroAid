import httpx
OPEN_METEO_URL="https://api.open-meteo.com/v1/forecast"

# Cliente compartido: reutiliza conexiones TCP/TLS entre requests
_clima_client: httpx.AsyncClient | None = None

def get_clima_client() -> httpx.AsyncClient:
    global _clima_client
    if _clima_client is None or _clima_client.is_closed:
        _clima_client = httpx.AsyncClient(timeout=10.0)
    return _clima_client

async def close_clima_client() -> None:
    global _clima_client
    if _clima_client is not None:
        await _clima_client.aclose()
        _clima_client = None

async def get_clima(lat:float,lon:float)->dict:
    params={
        "latitude":lat,
        "longitude":lon,
        "current": "temperature_2m,wind_speed_10m,rain",
        "daily": "temperature_2m_max,temperature_2m_min,rain_sum",
        "forecast_days":3,
        "timezone":"auto"
    }
    response=await get_clima_client().get(
        OPEN_METEO_URL,
        params=params
    )
    response.raise_for_status()
    data=response.json()
    current=data.get("current",{})
    daily=data.get("daily",{})
    forecast=[]
    dates=daily.get("time",[])
    temp_max=daily.get("temperature_2m_max",[])
    temp_min=daily.get("temperature_2m_min",[])
    rain_sum=daily.get("rain_sum",[])
    for i,date in enumerate(dates):
        forecast.append({
            "date":date,
            "temperature_max":temp_max[i]if i<len(temp_max) else None,
            "temperature_min":temp_min[i]if i<len(temp_min) else None,
            "rain":rain_sum[i]if i<len(rain_sum) else None,
        })
    return {
        "temperature":current.get("temperature_2m"),
        "wind":current.get("wind_speed_10m"),
        "rain":current.get("rain"),
        "forecast":forecast
    }