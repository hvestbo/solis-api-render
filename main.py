import os, json, hmac, hashlib, base64, requests
from flask import Flask, jsonify
from email.utils import formatdate

app = Flask(__name__)

API_ID    = os.getenv("SOLIS_KEYID", "").strip()
API_SECRET= os.getenv("SOLIS_SECRET", "").strip()
BASE      = "https://www.soliscloud.com:13333"

def content_md5_b64(body_bytes: bytes) -> str:
    m = hashlib.md5()
    m.update(body_bytes)
    return base64.b64encode(m.digest()).decode()

def sign_v2(method: str, content_md5: str, content_type: str, date_str: str, resource: str) -> str:
    canonical = f"{method}\n{content_md5}\n{content_type}\n{date_str}\n{resource}"
    digest = hmac.new(API_SECRET.encode("utf-8"),
                      canonical.encode("utf-8"),
                      hashlib.sha1).digest()
    return base64.b64encode(digest).decode()

def post_json(path: str, body_dict: dict, timeout=15):
    body_str   = json.dumps(body_dict, separators=(",", ":"))
    body_bytes = body_str.encode("utf-8")
    ctype      = "application/json;charset=UTF-8"
    date_str   = formatdate(timeval=None, usegmt=True)
    cmd5       = content_md5_b64(body_bytes)
    sign       = sign_v2("POST", cmd5, ctype, date_str, path)

    headers = {
        "Content-Type": ctype,
        "Content-MD5": cmd5,
        "Date": date_str,
        "Authorization": f"API {API_ID}:{sign}",
    }

    r = requests.post(f"{BASE}{path}", data=body_bytes, headers=headers, timeout=timeout)
    return r.status_code, r.text

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
    # 1) Hent stationId
    st_body = {"pageNo": "1", "pageSize": "10"}
    st_code, st_resp = post_json("/v1/api/userStationList", st_body)
    if st_code != 200:
        return jsonify({"step": "userStationList", "error": st_code, "resp": st_resp}), 502

    try:
        st_json = json.loads(st_resp)
        station_id = st_json["data"]["page"]["records"][0]["stationId"]
    except Exception as e:
        return jsonify({"step": "parseStationId", "error": str(e), "resp": st_resp}), 500

    # 2) Bruk stationId i inverterList
    inv_body = {"pageNo": "1", "pageSize": "10", "stationId": station_id}
    inv_code, inv_resp = post_json("/v1/api/inverterList", inv_body)
    if inv_code != 200:
        return jsonify({"step": "inverterList", "error": inv_code, "resp": inv_resp}), 502

    try:
        inv_json = json.loads(inv_resp)
        return jsonify(inv_json)
    except Exception as e:
        return jsonify({"step": "parseInverter", "error": str(e), "resp": inv_resp}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
