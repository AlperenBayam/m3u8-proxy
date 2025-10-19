#!/usr/bin/env python3
import requests
import re
import time
import logging
import traceback
from urllib.parse import urlparse, urljoin
from flask import Flask, request, Response

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def is_allowed_url(url):
    """Güvenli URL kontrolü"""
    try:
        parsed = urlparse(url)
        forbidden_netlocs = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
        if any(forbidden in parsed.netloc for forbidden in forbidden_netlocs):
            return False
        if parsed.scheme not in ('http', 'https'):
            return False
        return True
    except:
        return False

def smart_fetch(url):
    strategies = [
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://dengetv66.live/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        },
        # ... diğer stratejiler ...
    ]

    for i, headers in enumerate(strategies):
        try:
            logging.info(f"Strateji {i + 1} deneniyor: {url}")
            response = requests.get(url, headers=headers, timeout=30, verify=True)
            
            if response.status_code == 200:
                logging.info(f"Strateji {i + 1} başarılı")
                return {
                    'content': response.text,
                    'content_type': response.headers.get('content-type', ''),
                    'status': response.status_code
                }
            else:
                logging.warning(f"Strateji {i + 1} hata: {response.status_code}")
                time.sleep(1)
        except requests.exceptions.RequestException as e:
            logging.error(f"Strateji {i + 1} ağ hatası: {str(e)}")
            time.sleep(1)
        except Exception as e:
            logging.error(f"Strateji {i + 1} beklenmeyen hata: {str(e)}")
            time.sleep(1)
    
    return None

def resolve_url(file_path, base_url):
    """URL çözümleme fonksiyonu"""
    if file_path.startswith(('http://', 'https://')):
        return file_path
    if file_path.startswith('//'):
        return f'https:{file_path}'
    
    base_url_str = f"{base_url.scheme}://{base_url.netloc}"
    return urljoin(base_url_str + base_url.path, file_path)

@app.route('/')
def proxy():
    src = request.args.get('src')
    if not src:
        return "Hata: 'src' parametresi gerekli.", 400
    
    if not is_allowed_url(src):
        return "Hata: İzin verilmeyen URL.", 400

    try:
        logging.info(f'Proxy isteği: {src}')
        result = smart_fetch(src)
        
        if not result:
            return "Hata: İçerik alınamadı.", 502

        content = result['content']
        content_type = result['content_type']
        base_url_parsed = urlparse(src)

        # M3U8 işleme
        if 'mpegurl' in content_type or '.m3u8' in src:
            logging.info('M3U8 playlist işleniyor')

            def replace_segment(match):
                return resolve_url(match.group(1), base_url_parsed)

            # Tüm segmentleri ve playlistleri değiştir
            content = re.sub(r'(\S+\.(ts|m3u8))(?:\?[^#\s]*)?', replace_segment, content)
            
            # EXT-X-KEY URI'larını değiştir
            content = re.sub(
                r'#EXT-X-KEY:.*URI="([^"]+)"',
                lambda m: m.group(0).replace(m.group(1), resolve_url(m.group(1), base_url_parsed)),
                content
            )

            return Response(
                content,
                mimetype='application/vnd.apple.mpegurl',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/vnd.apple.mpegurl'
                }
            )
        else:
            # Diğer içerik türleri
            return Response(
                content,
                mimetype=content_type,
                headers={
                    'Cache-Control': 'public, max-age=3600',
                    'Access-Control-Allow-Origin': '*'
                }
            )

    except Exception as e:
        logging.error(f"Proxy hatası: {str(e)}\n{traceback.format_exc()}")
        return "İç sunucu hatası", 500

# CORS headers
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Range'
    return response

@app.route('/', methods=['OPTIONS'])
def handle_options():
    return '', 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
