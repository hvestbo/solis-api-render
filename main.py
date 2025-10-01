import os, json, hmac, hashlib, base64, requests
from flask import Flask, jsonify
from email.utils import formatdate

app = Flask(__name__)

API_ID     = os.getenv("SOLIS_KEYID", "").strip()
API_SECRET = os.getenv("SOLIS_SECRET", "").strip()
BASE       = "https://www.soliscloud.com:13333"

# Hjelpefunksjoner
def content_md5_b64(body_bytes: bytes) -> str:
    md5 = hashlib.md5()
    md5.update(body_bytes)
    return base64.b64encode(md5.digest()).decode()

def make_sign(method: str, content_md5: str, content_type: str, date_str: str, resource: str) -> str:
    canonical = f"{method}\n{content_md5}\n{content_type}\n{date_str}\n{resource}"
    digest = hmac.new(API_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()

def post_json_try(resource: str, body: dict, content_type_variant: str):
    # JSON må være helt kompakt (ingen ekstra whitespace), ellers matcher ikke MD5
    body_str   = json.dumps(body, separators=(",", ":"))
    body_bytes = body_str.encode("utf-8")
    date_str   = formatdate(timeval=None, usegmt=True)
    cmd5       = content_md5_b64(body_bytes)
    sign       = make_sign("POST", cmd5, content_type_variant, date_str, resource)

    headers = {
        "Content-Type": content_type_variant,
        "Content-MD5": cmd5,
        "Date": date_str,
        "Authorization": f"API {API_ID}:{sign}",
        "Accept": "application/json"
    }

    resp = requests.post(f"{BASE}{resource}", data=body_bytes, headers=headers, timeout=20)
    return resp

def post_json(resource: str, body: dict):
    """
    Prøv først 'application/json;charset=UTF-8'.
    Noen servere krever 'application/json; charset=UTF-8' (med mellomrom).
    """
    variants = ["application/json;charset=UTF-8", "application/json; charset=UTF-8"]
    last = None
    for ct in variants:
        r = post_json_try(resource, body, ct)
        if r.status_code == 200:
            return True, ct, r
        last = (ct, r.status_code, r.text[:2000])
        # Hvis signen var feil får vi 403/wrong sign – prøv neste variant
    return False, last[0], last  # (ok=False, brukt Content-Type, (ct, status, text))

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
    # 1) Hent stasjonsliste (verifiserer signaturen)
    ok, used_ct, res = post_json("/v1/api/userStationList", {"pageNo":"1","pageSize":"10"})
    if not ok:
        ct, status, text = res
        return jsonify({
            "step": "userStationList",
            "contentTypeTried": used_ct,
            "error": status,
            "text": text
        }), 502

    try:
        st = res.json()
        records = st["data"]["page"]["records"]
        if not records:
            return jsonify({"step":"userStationList","error":"no stations","raw":st}), 200
        station_id = records[0]["stationId"]
    except Exception as e:
        return jsonify({"step":"parseStationId","error":str(e),"raw":res.text[:2000]}), 500

    # 2) Hent invertere på stasjonen
    ok2, used_ct2, res2 = post_json("/v1/api/inverterList", {"pageNo":"1","pageSize":"10","stationId":station_id})
    if not ok2:
        ct, status, text = res2
        return jsonify({
            "step": "inverterList",
            "contentTypeTried": used_ct2,
            "error": status,
            "text": text
        }), 502

    # Returnér rå inverter-JSON først, så ser vi feltnavnene eksakt
    return jsonify(res2.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
