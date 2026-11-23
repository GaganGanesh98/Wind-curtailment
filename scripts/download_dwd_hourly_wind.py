import re, time, pathlib, urllib.request

BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/"
OUT = pathlib.Path("data/raw/dwd/hourly_wind")
START = 20211001

def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print("  retry", i + 1, "after", type(e).__name__); time.sleep(10 * (i + 1))

for sub in ("historical/", "recent/"):
    d = OUT / sub.strip("/"); d.mkdir(parents=True, exist_ok=True)
    html = get(BASE + sub).decode("latin-1")
    files = sorted(set(re.findall(r'href="([^"]+\.(?:zip|txt))"', html)))
    n = 0
    for f in files:
        if f.endswith(".zip") and sub == "historical/":
            m = re.search(r"_(\d{8})_(\d{8})_hist\.zip$", f)
            if not m or int(m.group(2)) < START:
                continue                      # station closed before Oct 2021
        if (d / f).exists():
            continue
        (d / f).write_bytes(get(BASE + sub + f)); n += 1
        print(sub, f); time.sleep(0.2)
    print(sub, "downloaded", n)
