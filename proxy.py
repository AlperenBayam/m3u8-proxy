#!/usr/bin/env python3
# flask_proxy_with_residential_rotation.py
import time
import random
import logging
import threading
from urllib.parse import urlparse, urljoin
from flask import Flask, request, Response
import httpx
from cachetools import TTLCache

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# ---------- CONFIG ----------
# REQUIRED: residence proxy list from provider (http(s) format, may include user:pass@host:port)
PROXY_LIST = [
    # Example: 'http://user:pass@res-proxy1.example.com:10000',
    # 'http://user:pass@res-proxy2.example.com:10000',
]
# Eğer boşsa doğrudan çıkış (riskli - muhtemelen ban olur)
USE_PROXIES = len(PROXY_LIST) > 0

# Per-src session mapping (to keep same proxy for that playlist/session)
SRC_TO_PROXY = {}  # {src: proxy_url}
SRC_PROXY_TTL = 60  # seconds, token might be short lived — keep mapping short

# Cache to store mapping with TTL
src_cache = TTLCache(maxsize=1000, ttl=SRC_PROXY_TTL)

# Keep httpx.Client objects per proxy (for connection reuse)
proxy_clients = {}  # {proxy_url: httpx.Client}
proxy_health = {}   # {proxy_url: {'good': True/False, 'last_checked': timestamp}}

# User-Agent pool and header strategies
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]
REFERER_DEFAULT = "https://dengetv66.live/"

# HTTP client options
HTTP_TIMEOUT = 30.0
MAX_RETRIES = 2

# Healthcheck interval
HEALTHCHECK_INTERVAL = 30

# Concurrency control (per proxy)
MAX_PARALLEL_PER_PROXY = 6
proxy_locks = {}  # semaphore like counters {proxy_url: current_parallel}

# ---------- HELPERS ----------
def init_proxy_clients():
    if not USE_PROXIES:
        logging.warning("No proxies configured — requests will go direct (high ban risk).")
        return
    for p in PROXY_LIST:
        if p not in proxy_clients:
            # Create a client with proxy configured
            # Note: httpx proxy format uses dict, but we can set up per-request too.
            client = httpx.Client(proxies=p, timeout=HTTP_TIMEOUT, http2=True, limits=httpx.Limits(max_keepalive_connections=10, max_connections=100))
            proxy_clients[p] = client
            proxy_health[p] = {'good': True, 'last_checked': 0}
            proxy_locks[p] = 0
    logging.info(f"Initialized {len(proxy_clients)} proxy clients.")

def pick_healthy_proxy():
    """Pick a proxy that is marked healthy, randomize to avoid patterns."""
    healthy = [p for p, h in proxy_health.items() if h.get('good', False)]
    if not healthy:
        # fallback to all proxies if none healthy or proxies empty
        healthy = list(proxy_clients.keys())
    if not healthy:
        return None
    return random.choice(healthy)

def mark_proxy_bad(proxy):
    if proxy in proxy_health:
        proxy_health[proxy]['good'] = False
        proxy_health[proxy]['last_checked'] = time.time()
        logging.warning(f"Marked proxy BAD: {proxy}")

def mark_proxy_good(proxy):
    if proxy in proxy_health:
        proxy_health[proxy]['good'] = True
        proxy_health[proxy]['last_checked'] = time.time()

def proxy_health_check_worker():
    while True:
        for p, client in list(proxy_clients.items()):
            try:
                # lightweight HEAD to google or a fast domain to verify connectivity
                resp = client.get("https://www.google.com/generate_204", timeout=10.0)
                if resp.status_code in (204, 200):
                    mark_proxy_good(p)
                else:
                    mark_proxy_bad(p)
            except Exception as e:
                mark_proxy_bad(p)
        time.sleep(HEALTHCHECK_INTERVAL)

def resolve_url(file_path, base_url):
    if file_path.startswith(('http://', 'https://')):
        return file_path
    if file_path.startswith('//'):
        return 'https:' + file_path
    base_url_str = f"{base_url.scheme}://{base_url.netloc}"
    return urljoin(base_url_str + base_url.path, file_path)

def get_client_for_src(src):
    """Return client and proxy used for this src (keep sticky session for short TTL)."""
    if not USE_PROXIES:
        return None, None
    # sticky mapping
    if src in src_cache:
        proxy = src_cache[src]
        if proxy in proxy_clients and proxy_health.get(proxy, {}).get('good', False):
            return proxy_clients[proxy], proxy
    # choose a healthy one
    proxy = pick_healthy_proxy()
    if not proxy:
        return None, None
    src_cache[src] = proxy
    return proxy_clients[proxy], proxy

def fetch_with_retries(client, url, headers=None, stream=False):
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            if stream:
                return client.stream("GET", url, headers=headers, timeout=HTTP_TIMEOUT)
            else:
                return client.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        except httpx.RequestError as e:
            last_exc = e
            logging.warning(f"Request error (attempt {attempt}) for {url}: {e}")
            time.sleep(0.5 + random.random()*0.5)
    raise last_exc

# ---------- INIT ----------
init_proxy_clients()
# start healthcheck thread if proxies exist
if USE_PROXIES:
    t = threading.Thread(target=proxy_health_check_worker, daemon=True)
    t.start()

# ---------- ROUTES ----------
@app.route('/')
def proxy_index():
    src = request.args.get('src')
    if not src:
        return "Hata: 'src' parametresi gerekli.", 400

    # Basic URL validation
    try:
        parsed = urlparse(src)
        if parsed.scheme not in ('http', 'https'):
            return "Hata: Geçersiz protokol.", 400
    except Exception:
        return "Hata: Geçersiz URL.", 400

    # Determine client (proxy) to use for this src
    client, proxy_used = get_client_for_src(src)

    # Headers: rotate UA and set sensible headers similar to browser
    headers = {
        "User-Agent": random.choice(UA_POOL),
        "Referer": REFERER_DEFAULT,
        "Accept": "*/*",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    # Add tiny jitter to avoid super-regular pattern
    time.sleep(random.uniform(0.05, 0.2))

    try:
        logging.info(f"Proxy fetch src={src} via proxy={proxy_used}")
        if client:
            resp = fetch_with_retries(client, src, headers=headers)
        else:
            # direct
            with httpx.Client(timeout=HTTP_TIMEOUT, http2=True) as direct_client:
                resp = fetch_with_retries(direct_client, src, headers=headers)

        # If we get Cloudflare-ish status codes, mark proxy bad and return helpful info
        if resp.status_code in (403, 429, 520, 521, 522, 523, 524):
            logging.warning(f"Received {resp.status_code} from origin for {src} via {proxy_used}")
            if proxy_used:
                mark_proxy_bad(proxy_used)
            # return origin body to help diagnose
            body = resp.text if hasattr(resp, 'text') else ''
            return Response(body, status=resp.status_code, mimetype='text/html')

        content_type = resp.headers.get('content-type', '') or ''
        content = resp.text if not isinstance(resp, httpx.Response) or not resp.is_stream_consumed else resp.content

        # M3U8 handling (very similar to senin mantığın)
        if 'mpegurl' in content_type or src.endswith('.m3u8') or '.m3u8' in src:
            base_url_parsed = urlparse(src)

            def replace_segment(match):
                seg = match.group(1)
                if not seg.startswith('http'):
                    return resolve_url(seg, base_url_parsed)
                return seg

            # segments
            import re
            content_str = content if isinstance(content, str) else content.decode('utf-8', errors='ignore')

            # convert relative to absolute, then rewrite to our /seg endpoint
            def make_abs_and_proxy(m):
                line = m.group(1)
                if line.startswith('#'): return m.group(0)
                seg = line.strip()
                full = seg
                try:
                    from urllib.parse import urljoin
                    newfull = urljoin(src, seg)
                    full = newfull
                except:
                    full = seg
                proxied = f"{request.url_root}seg?src={httpx.utils.quote(full, safe='')}"
                return proxied

            rewritten = re.sub(r'^(?!#)(.+)$', lambda mm: make_abs_and_proxy(mm), content_str, flags=re.M)

            return Response(rewritten, mimetype='application/vnd.apple.mpegurl', headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Access-Control-Allow-Origin': '*'
            })

        # Generic content return
        content_bytes = content.encode('utf-8') if isinstance(content, str) else content
        return Response(content_bytes, mimetype=content_type or 'application/octet-stream', headers={
            'Content-Length': str(len(content_bytes)),
            'Cache-Control': 'public, max-age=3600',
            'Access-Control-Allow-Origin': '*'
        })

    except Exception as e:
        logging.exception("Proxy hata")
        if proxy_used:
            mark_proxy_bad(proxy_used)
        return "İç sunucu hatası", 500

@app.route('/seg')
def seg_endpoint():
    src = request.args.get('src')
    if not src:
        return "Hata: 'src' parametresi gerekli.", 400
    target = httpx.utils.unquote(src)
    # Use same proxy mapping as playlist if possible
    parsed_origin = request.args.get('origin')  # optional
    client, proxy_used = get_client_for_src(parsed_origin or target)

    # headers mimic browser and include referer if provided
    headers = {
        "User-Agent": random.choice(UA_POOL),
        "Referer": parsed_origin or REFERER_DEFAULT,
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    # concurrency guard per proxy
    if proxy_used:
        # simple counter guard
        if proxy_locks.get(proxy_used, 0) >= MAX_PARALLEL_PER_PROXY:
            # brief wait to reduce parallelism
            time.sleep(0.1 + random.random()*0.2)

    try:
        logging.info(f"Segment fetch {target} via {proxy_used}")
        if client:
            stream = client.stream("GET", target, headers=headers, timeout=HTTP_TIMEOUT)
            with stream as r:
                if r.status_code in (403, 429, 520, 521, 522):
                    mark_proxy_bad(proxy_used)
                    body = r.text
                    return Response(body, status=r.status_code, mimetype='text/html')
                # forward headers selectively
                resp = Response(r.iter_bytes(), status=r.status_code)
                content_type = r.headers.get('content-type')
                if content_type:
                    resp.headers['Content-Type'] = content_type
                resp.headers['Access-Control-Allow-Origin'] = '*'
                resp.headers['Cache-Control'] = 'public, max-age=86400'
                return resp
        else:
            with httpx.stream("GET", target, headers=headers, timeout=HTTP_TIMEOUT) as r:
                if r.status_code in (403, 429, 520, 521, 522):
                    body = r.text
                    return Response(body, status=r.status_code, mimetype='text/html')
                resp = Response(r.iter_bytes(), status=r.status_code)
                ct = r.headers.get('content-type')
                if ct:
                    resp.headers['Content-Type'] = ct
                resp.headers['Access-Control-Allow-Origin'] = '*'
                resp.headers['Cache-Control'] = 'public, max-age=86400'
                return resp
    except Exception as e:
        logging.exception("Segment fetch hata")
        if proxy_used:
            mark_proxy_bad(proxy_used)
        return "Segment fetch error", 502

# CORS preflight and after_request
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, HEAD'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Range, Accept-Encoding, X-Requested-With'
    return response

@app.route('/health')
def health():
    return {'status':'ok', 'time': time.time()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
