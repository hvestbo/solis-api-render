import os, time, hmac, hashlib, requests
from flask import Flask, jsonify

app = Flask(__name__)

SOLIS_KEYID   = os.getenv("SOLIS_KEYID", "").strip()
SOLIS_SECRET  = os.getenv("SOLIS_SECRET", "").strip()

BASE = "https://www.soliscloud.com:13333"

def sign_headers(params: dict):
    ts = str(int(time.time() * 1000))
    sitems = [f"{k}={params[k]}" for k in sorted(params.keys())]
    pstr = "&".join(sitems)
    sign_str = f"{SOLIS_KEYID}{ts}{pstr}{SOLIS_SECRET}"
    signature = hmac.new(SOLIS_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()
    headers = {
        "Content-Type": "application/json",
        "keyId": SOLIS_KEYID,
        "sign": signature,
        "timeStamp": ts
    }
    return headers

def fetch_inverters():
    params = {"pageNo": 1, "pageSize": 10}
    h = sign_headers(params)
    r = requests.post(f"{BASE}/v1/api/inverterList", json=params, headers=h, timeout=15)
    return r.json() if r.status_code == 200 else {"error": r.status_code, "text": r.text}

@app.route("/")
def root():
    return "✅ Solis API backend kjører. Bruk /solis_api"

@app.route("/solis_api")
def solis_api():
    data = fetch_inverters()
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
