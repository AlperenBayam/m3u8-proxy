#!/usr/bin/env python3
import requests
import re
import os
import time
import logging
from urllib.parse import urlparse, urljoin
from flask import Flask, request, Response, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def smart_fetch(url):
    """Akıllı fetch fonksiyonu - 403 bypass ile"""
    strategies = [
        {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://dengetv66.live/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        },
        {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://mactadi2.blogspot.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        },
        {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'http://localhost:3000/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        },
        {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.google.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        },
        {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://sportsobama.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        },
        {
            'User-Agent': 'Mozilla/5.0',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Cache-Control': 'no-cache'
        }
    ]

    for i, headers in enumerate(strategies):
        try:
            logging.info(f"Strateji {i + 1} deneniyor...")
            response = requests.get(url, headers=headers, timeout=30, verify=True)
            logging.info(f"Strateji {i + 1} status: {response.status_code}")

            if response.status_code == 200:
                logging.info(f"Strateji {i + 1} başarılı!")
                return {
                    'content': response.text,
                    'content_type': response.headers.get('content-type', ''),
                    'status': response.status_code
                }
            elif response.status_code == 403:
                logging.warning(f"Strateji {i + 1} 403 hatası, bir sonraki deneniyor...")
                time.sleep(1)
            else:
                logging.warning(f"Strateji {i + 1} hata: {response.status_code}")
        except Exception as e:
            logging.error(f"Strateji {i + 1} exception: {str(e)}")
            time.sleep(1)
    return False

def resolve_url(file_path, base_url):
    if file_path.startswith('http'):
        return file_path
    if file_path.startswith('//'):
        return f'https:{file_path}'
    if file_path.startswith('/'):
        return f"{base_url.scheme}://{base_url.netloc}{file_path}"
    base_path = '/'.join(base_url.path.split('/')[:-1])
    return f"{base_url.scheme}://{base_url.netloc}/{base_path}/{file_path}".replace('//', '/')

@app.route('/')
def proxy():
    src = request.args.get('src')
    if not src:
        return "Hata: 'src' parametresi gerekli.", 400

    try:
        parsed_url = urlparse(src)
        if not parsed_url.scheme or not parsed_url.netloc:
            return "Hata: Geçersiz URL formatı.", 400
    except:
        return "Hata: Geçersiz URL formatı.", 400

    logging.info(f'Proxy başlıyor: {src}')
    result = smart_fetch(src)
    if not result:
        return "Hata: Tüm stratejiler başarısız.", 500

    content = result['content']
    content_type = result['content_type']
    base_url = urlparse(src)

    if 'mpegurl' in content_type or '.m3u8' in src:
        logging.info('M3U8 playlist tespit edildi')

        def replace_ts(match):
            return resolve_url(match.group(1), base_url)

        def replace_m3u8(match):
            return resolve_url(match.group(1), base_url)

        def replace_img(match):
            img_url = match.group(1)
            if not img_url.startswith('http'):
                img_url = resolve_url(img_url, base_url)
            return f"{request.url_root}?src={img_url}"

        def replace_key(match):
            key_url = resolve_url(match.group(1), base_url)
            return match.group(0).replace(match.group(1), key_url)

        content = re.sub(r'(\S+\.ts)(?:\?[^#\s]*)?', replace_ts, content)
        content = re.sub(r'(\S+\.m3u8)(?:\?[^#\s]*)?', replace_m3u8, content)
        content = re.sub(r'(\S+\.(jpg|jpeg|png|webp|gif))(?:\?[^#\s]*)?', replace_img, content)
        content = re.sub(r'#EXT-X-KEY:.*URI="([^"]+)"', replace_key, content)

        return Response(
            content,
            mimetype='application/vnd.apple.mpegurl',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Content-Type': 'application/vnd.apple.mpegurl',
                'Accept-Ranges': 'bytes'
            }
        )
    else:
        content_bytes = content.encode('utf-8')
        return Response(
            content_bytes,
            mimetype=content_type if content_type else 'application/octet-stream',
            headers={
                'Content-Length': str(len(content_bytes)),
                'Cache-Control': 'public, max-age=3600'
            }
        )

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Range,Accept-Encoding,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
    response.headers.add('Access-Control-Expose-Headers', 'Content-Length,Content-Range,Accept-Ranges')
    response.headers.add('Access-Control-Max-Age', '86400')
    return response

@app.route('/', methods=['OPTIONS'])
def handle_options():
    return '', 200

if __name__ == '__main__':
    app.run(debug=True)
