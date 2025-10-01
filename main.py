import os, time, json, hmac, hashlib, base64, requests
from flask import Flask, jsonify
from email.utils import formatdate

app = Flask(__name__)

API_ID    = os.getenv("SOLIS_KEYID", "").strip()
API_SECRET= os.getenv("SOLIS_SECRET", "").strip()
BASE      = "https://www.soliscloud.com:13333"
RESOURCE  = "/v1/api/inverterList"   # canonicalized resource for signing

def content_md5_b64(body_bytes: bytes) -> str:
    m = hashlib.md5()
    m.update(body_bytes)
    return base64.b64encode(m.digest()).decode()

def sign_v2(method: str, content_md5: str, content_type: str, date_str: str, resource: str) -> str:
    """
    Sign = base64(HmacSHA1(apiSecret,
            METHOD + "\n" + Content-MD5 + "\n" + Content-Type + "\n" + Date + "\n" + CanonicalizedResource))
    """
    canonical = f"{method}\n{content_md5}\n{content_type}\n{date_str}\n{resource}"
    digest = hmac.new(API_SECRET.encode("utf-8"),
                      canonical.encode("utf-8"),
                      hashlib.sha1).digest()
    return base64.b64encode(digest).decode()

def post_json(path: str, body_dict: dict, timeout=15):
    # NB: JSON må serialiseres *nøyaktig* slik vi signerer; bruk kompakt form.
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
    ok = r.status_code == 200
    return ok, r

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
    # API-dokumentet sier pageNo/pageSize er påkrevd; stationId er valgfri.
    body = {"pageNo":"1","pageSize":"10"}  # bruk str iht. tabellen i spec
    ok, resp = post_json(RESOURCE, body)

    if not ok:
        # Returner nyttig feilsvar for videre feilsøking
        return jsonify({
            "error": resp.status_code,
            "text": resp.text[:2000],
            "sentTo": RESOURCE
        }), 502

    data = resp.json()
    # Hvis dette er første kall: bare returnér rå data, så vi ser feltnavnene eksakt
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
