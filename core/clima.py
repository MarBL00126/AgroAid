import httpx
OPEN_METEO_URL="https://api.open-meteo.com/v1/forecast"

async def get_clima(lat:float,lon:float)->dict:
    params={
        "latitude":lat,
        "longitude":lon,
        "current": "temperature_2m,wind_speed_10m,rain",
        "daily": "temperature_2m_max,temperature_2m_min,rain_sum",
        "forecast_days":3,
        "timezone":"auto"
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response=await client.get(
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