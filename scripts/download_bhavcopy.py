import requests
import time
from pathlib import Path
from datetime import datetime

SAVE_DIR = Path("Bhavcopy")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.utcnow()

# Skip Saturday/Sunday

if today.weekday() >= 5:
    print("Weekend - Market Closed")
    raise SystemExit(0)

date_str = today.strftime("%d%m%Y")

filename = f"sec_bhavdata_full_{date_str}.csv"

file_path = SAVE_DIR / filename

# Prevent duplicate download

if file_path.exists():
    print(f"{filename} already exists")
    raise SystemExit(0)

url = (
f"https://nsearchives.nseindia.com/"
f"products/content/{filename}"
)

headers = {
"User-Agent": (
"Mozilla/5.0 "
"(Windows NT 10.0; Win64; x64)"
),
"Referer": "https://www.nseindia.com/"
}

MAX_RETRIES = 20

for attempt in range(MAX_RETRIES):

print(
    f"Attempt {attempt + 1}/{MAX_RETRIES}"
)

try:

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    if response.status_code == 200:

        with open(
            file_path,
            "wb"
        ) as f:

            f.write(
                response.content
            )

        print(
            f"Downloaded {filename}"
        )

        break

    print(
        f"HTTP {response.status_code}"
    )

except Exception as e:

    print(e)

time.sleep(60)


else:


raise Exception(
    "File not available "
    "after 20 retries."
)
