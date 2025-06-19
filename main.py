import os, time, hmac, hashlib, requests
from flask import Flask, jsonify
from cachetools import TTLCache

app = Flask(__name__)
cache = TTLCache(maxsize=1, ttl=300)  # 5 minutter

SOLIS_KEYID = os.getenv('SOLIS_KEYID')
SOLIS_SECRET = os.getenv('SOLIS_SECRET')
SOLIS_USERID = os.getenv('SOLIS_USERID')

API_URL = 'https://www.soliscloud.com:13333/v1/api/inverterList'

def fetch_data():
    timestamp = str(int(time.time() * 1000))
    params = {'pageNo': 1, 'pageSize': 1}
    param_str = '&'.join(f'{k}={params[k]}' for k in sorted(params))
    sign_str = SOLIS_KEYID + timestamp + param_str + SOLIS_SECRET
    sign = hmac.new(SOLIS_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()
    headers = {
        'Content-Type': 'application/json',
        'keyId': SOLIS_KEYID,
        'sign': sign,
        'timeStamp': timestamp
    }
    
    print("DEBUG SIGN:", sign_str)
    print("DEBUG PARAMS:", param_str)
    print("DEBUG HEADERS:", headers)
    print("DEBUG BODY:", params)
    resp = requests.post(API_URL, json=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

@app.route('/solis_api')
def solis_api():
    if 'data' not in cache:
        raw = fetch_data()
        # TODO: bytt dummyverdier mot ekte uttak i raw
        nowKw = raw.get('data', [{}])[0].get('currentPower', 0) / 1000
        todayKWh = raw.get('data', [{}])[0].get('todayEnergy', 0) / 1000
        totalKWh = raw.get('data', [{}])[0].get('totalEnergy', 0) / 1000
        co2 = round(totalKWh * 0.00045, 2)
        cache['data'] = {
            'nowKw': round(nowKw, 2),
            'todayKWh': round(todayKWh, 2),
            'totalMWh': round(totalKWh / 1000, 2),
            'co2SavedTons': co2,
            'treesPlanted': int(co2 * 40),
            'kmSaved': int(co2 * 4444),
            'updatedAt': time.strftime('%H:%M'),
            'chartData': [42,38,50,35,48,55,47]
        }
    return jsonify(cache['data'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
