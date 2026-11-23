import pathlib, cdsapi

OUT = pathlib.Path("data/raw/era5"); OUT.mkdir(parents=True, exist_ok=True)
VARS = ["100m_u_component_of_wind", "100m_v_component_of_wind",
        "10m_u_component_of_wind", "10m_v_component_of_wind",
        "2m_temperature", "surface_pressure", "instantaneous_10m_wind_gust"]
AREA = [55.2, 5.8, 47.2, 15.1]            # N, W, S, E: Germany
months = [(y, m) for y in range(2021, 2027) for m in range(1, 13)
          if (2021, 10) <= (y, m) <= (2026, 9)]

c = cdsapi.Client()
for y, m in months:
    target = OUT / f"era5_de_{y}{m:02d}.nc"
    if target.exists():
        continue
    print("requesting", y, m, flush=True)
    c.retrieve("reanalysis-era5-single-levels", {
        "product_type": ["reanalysis"],
        "variable": VARS,
        "year": [str(y)], "month": [f"{m:02d}"],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": AREA,
        "data_format": "netcdf", "download_format": "unarchived",
    }, str(target))
print("done", flush=True)
