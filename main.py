import os, json, hmac, hashlib, base64, requests
from flask import Flask, jsonify
from email.utils import formatdate

app = Flask(__name__)

API_ID     = os.getenv("SOLIS_KEYID", "").strip()
API_SECRET = os.getenv("SOLIS_SECRET", "").strip()

HOSTS = [
    "https://api.soliscloud.com:13333",
    "https://www.soliscloud.com:13333",
    "https://eu.soliscloud.com:13333",
]

CT_VARIANTS = [
    "application/json;charset=UTF-8",
    "application/json; charset=UTF-8",
]

def content_md5_b64(body_bytes: bytes) -> str:
    md5 = hashlib.md5()
    md5.update(body_bytes)
    return base64.b64encode(md5.digest()).decode()

def sign_v2(method: str, cmd5: str, ctype: str, date_str: str, resource: str) -> str:
    canonical = f"{method}\n{cmd5}\n{ctype}\n{date_str}\n{resource}"
    digest = hmac.new(API_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()

def post_json(host: str, resource: str, body: dict, ctype: str, timeout=20):
    body_str   = json.dumps(body, separators=(",", ":"))  # eksakt JSON
    body_bytes = body_str.encode("utf-8")
    date_str   = formatdate(timeval=None, usegmt=True)
    cmd5       = content_md5_b64(body_bytes)
    sign       = sign_v2("POST", cmd5, ctype, date_str, resource)
    headers = {
        "Content-Type": ctype,
        "Content-MD5": cmd5,
        "Date": date_str,
        "Authorization": f"API {API_ID}:{sign}",
        "Accept": "application/json",
    }
    url = f"{host}{resource}"
    r = requests.post(url, data=body_bytes, headers=headers, timeout=timeout)
    return r

def try_user_station_list():
    errors = []
    body = {"pageNo":"1","pageSize":"10"}  # ingen userId i denne v2-varianten
    resource = "/v1/api/userStationList"
    for host in HOSTS:
        for ct in CT_VARIANTS:
            r = post_json(host, resource, body, ct)
            if r.status_code == 200:
                return True, host, ct, r
            errors.append({
                "host": host,
                "contentType": ct,
                "status": r.status_code,
                "text": r.text[:800]
            })
    return False, None, None, errors

def try_inverter_list(host: str, station_id: str, ct: str):
    body = {"pageNo":"1","pageSize":"10","stationId": station_id}
    resource = "/v1/api/inverterList"
    r = post_json(host, resource, body, ct)
    return r

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp

@app.route("/")
def root():
    return "✅ Solis API backend OK. Bruk /solis_api"

@app.route("/solis_api")
def solis_api():
    ok, host, ct, res = try_user_station_list()
    if not ok:
        return jsonify({"step":"userStationList","tried":res}), 502

    try:
        st = res.json()
        records = st["data"]["page"]["records"]
        if not records:
            return jsonify({"step":"userStationList","error":"no stations","raw":st}), 200
        station_id = records[0]["stationId"]
    except Exception as e:
        return jsonify({"step":"parseStationId","error":str(e),"raw":res.text[:800]}), 500

    r2 = try_inverter_list(host, station_id, ct)
    if r2.status_code != 200:
        return jsonify({
            "step":"inverterList",
            "hostUsed": host,
            "contentTypeUsed": ct,
            "status": r2.status_code,
            "text": r2.text[:800]
        }), 502

    return jsonify(r2.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
