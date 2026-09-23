import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

API_KEY = os.getenv("MOUSER_API_KEY")
BASE_URL = "https://api.mouser.com/api/v1"

# 代理设置（本地可选，Render 上不需要设置，留空即可）
PROXIES = None
http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
if http_proxy or https_proxy:
    PROXIES = {"http": http_proxy, "https": https_proxy or http_proxy}

HEADERS = {"Content-Type": "application/json"}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def keyword_search(part):
    url = f"{BASE_URL}/search/keyword"
    params = {"apiKey": API_KEY}
    payload = {
        "SearchByKeywordRequest": {
            "keyword": part,
            "records": 50,
            "startingRecord": 0,
            "searchOptions": "",
            "searchWithMyLanguage": ""
        }
    }
    r = requests.post(url, params=params, headers=HEADERS,
                      json=payload, timeout=30, proxies=PROXIES)
    return (r.json().get("SearchResults") or {}).get("Parts") or []

def partnumber_search(part):
    url = f"{BASE_URL}/search/partnumber"
    params = {"apiKey": API_KEY}
    payload = {
        "SearchByPartRequest": {
            "mouserPartNumber": part,
            "partSearchOptions": "None"
        }
    }
    r = requests.post(url, params=params, headers=HEADERS,
                      json=payload, timeout=30, proxies=PROXIES)
    return (r.json().get("SearchResults") or {}).get("Parts") or []

@app.route('/api/query')
def query():
    part = request.args.get('partNumber', '').strip()
    if not part:
        return jsonify({"error": "请输入型号"}), 400

    try:
        parts = keyword_search(part)

        has_price = any(p.get("PriceBreaks") for p in parts)
        if not has_price:
            try:
                exact_parts = partnumber_search(part)
                existing = {p.get("MouserPartNumber") for p in parts}
                for ep in exact_parts:
                    if ep.get("MouserPartNumber") not in existing:
                        parts.append(ep)
            except Exception as e:
                print("精确搜索失败:", e)

        if not parts:
            return jsonify({"error": "未找到该型号"}), 404

        best = None
        for p in parts:
            if p.get("PriceBreaks"):
                best = p
                break
        if best is None:
            best = parts[0]

        return jsonify({
            "partNumber": best.get("ManufacturerPartNumber"),
            "manufacturer": best.get("Manufacturer"),
            "description": best.get("Description"),
            "priceBreaks": best.get("PriceBreaks"),
            "detailUrl": best.get("ProductDetailUrl")
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "连接贸泽超时"}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"网络错误: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
