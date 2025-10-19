#!/usr/bin/env python3
import requests
import re
import os
from urllib.parse import urlparse, urljoin
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

def smart_fetch(url):
    """Akıllı fetch fonksiyonu - 403 bypass ile"""
    strategies = [
        # Strateji 1: dengetv66.live referer
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://dengetv66.live/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache'
        },
        # Strateji 2: mactadi referer
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://mactadi2.blogspot.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        },
        # Strateji 3: localhost referer
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'http://localhost:3000/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        },
        # Strateji 4: Google referer
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        },
        # Strateji 5: sportsobama.com referer
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://sportsobama.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        },
        # Strateji 6: Hiç referer yok
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        }
    ]

    for i, headers in enumerate(strategies):
        try:
            print(f"Strateji {i + 1} deneniyor...")
            
            response = requests.get(url, headers=headers, timeout=30, verify=False)
            
            print(f"Strateji {i + 1} status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"Strateji {i + 1} başarılı!")
                return {
                    'content': response.text,
                    'content_type': response.headers.get('content-type', ''),
                    'status': response.status_code
                }
            elif response.status_code == 403 and i < len(strategies) - 1:
                print(f"Strateji {i + 1} 403 hatası, bir sonraki strateji deneniyor...")
                import time
                time.sleep(1)  # 1 saniye bekleme
                continue
            else:
                print(f"Strateji {i + 1} başka hata: {response.status_code}")
                continue
                
        except Exception as e:
            print(f"Strateji {i + 1} exception: {str(e)}")
            if i < len(strategies) - 1:
                import time
                time.sleep(1)
                continue
    
    return False

def resolve_url(file_path, base_url):
    """URL çözümleme fonksiyonu"""
    if file_path.startswith('http'):
        return file_path
    if file_path.startswith('//'):
        return f'https:{file_path}'
    if file_path.startswith('/'):
        return f"{base_url.scheme}://{base_url.netloc}{file_path}"
    
    base_path = '/'.join(base_url.path.split('/')[:-1])
    return f"{base_url.scheme}://{base_url.netloc}{base_path}/{file_path}".replace('//', '/')

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
    
    print(f'Proxy başlıyor: {src}')
    
    result = smart_fetch(src)
    
    if not result:
        return "Hata: Tüm stratejiler başarısız.", 500
    
    content = result['content']
    content_type = result['content_type']
    
    # M3U8 playlist ise
    if 'mpegurl' in content_type or '.m3u8' in src:
        print('M3U8 playlist tespit edildi')
        
        base_url = urlparse(src)
        
        # TS dosyalarını ORİJİNAL hâlinde bırak
        def replace_ts(match):
            ts_url = resolve_url(match.group(1), base_url)
            return ts_url
        
        content = re.sub(r'(\S+\.ts)(?:\?[^#\s]*)?', replace_ts, content)
        
        # M3U8 dosyalarını ORİJİNAL hâlinde bırak
        def replace_m3u8(match):
            m3u8_url = resolve_url(match.group(1), base_url)
            return m3u8_url
        
        content = re.sub(r'(\S+\.m3u8)(?:\?[^#\s]*)?', replace_m3u8, content)
        
        # Resim dosyalarını ORİJİNAL hâlinde bırak
        def replace_img(match):
            img_url = match.group(1)
            if not img_url.startswith('http'):
                img_url = resolve_url(img_url, base_url)
            return img_url
        
        content = re.sub(r'(\S+\.(jpg|jpeg|png|webp|gif))(?:\?[^#\s]*)?', replace_img, content)
        
        # EXT-X-KEY: key URI'sini ORİJİNAL hâline getir
        def replace_key(match):
            key_url = resolve_url(match.group(1), base_url)
            return match.group(0).replace(match.group(1), key_url)
        
        content = re.sub(r'#EXT-X-KEY:.*URI="([^"]+)"', replace_key, content)
        
        response = Response(
            content,
            mimetype='application/vnd.apple.mpegurl',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Content-Disposition': 'inline',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, HEAD',
                'Access-Control-Allow-Headers': 'Content-Type, Range, Accept-Encoding',
                'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
                'Access-Control-Allow-Credentials': 'true',
                'Content-Type': 'application/vnd.apple.mpegurl'
            }
        )
        return response
    else:
        # Diğer içerik türleri
        response = Response(
            content,
            mimetype=content_type if content_type else 'application/octet-stream',
            headers={
                'Content-Length': str(len(content)),
                'Cache-Control': 'public, max-age=3600',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, HEAD',
                'Access-Control-Allow-Headers': 'Content-Type, Range, Accept-Encoding',
                'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
                'Access-Control-Allow-Credentials': 'true'
            }
        )
        return response

@app.after_request
def after_request(response):
    # CORS header'larını SADECE BURADA ekleyin
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Range,Accept-Encoding')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
    response.headers.add('Access-Control-Expose-Headers', 'Content-Length,Content-Range')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/', methods=['OPTIONS'])
def handle_options():
    return '', 200

# Vercel için gerekli
if __name__ == '__main__':
    app.run(debug=True)