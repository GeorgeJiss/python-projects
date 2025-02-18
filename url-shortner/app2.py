import string
import random
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

app = FastAPI()

if os.path.exists("urls.json"):
    with open("urls.json", "r") as f:
        try:
            url_db = json.load(f)
        except json.JSONDecodeError:
            url_db = {}  # Handle corrupted file
else:
    url_db = {}

def generate_short_code(length = 6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@app.post("/shorten/")
def shorten_url(request: Request, long_url: str):
    short_code = generate_short_code()
    url_db[short_code] = long_url

    with open("urls.json", "w") as f:
        json.dump(url_db, f)

    return f"Shortened URL: {request.base_url}{short_code}"


@app.get("/{short_code}")
def redirect_url(short_code: str):
    long_url = url_db.get(short_code)  # Get URL safely

    if long_url:  # Ensure it exists
        return RedirectResponse(url=long_url, status_code=302)
    
    raise HTTPException(status_code=404, detail="Short URL not found")