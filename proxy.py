#!/usr/bin/env python3
import requests
import re
import time
import logging
import traceback
from urllib.parse import urlparse, urljoin
from flask import Flask, request, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(name)
logging.basicConfig(level=logging.INFO)

def create_session():
"""Oturum oluştur ve retry stratejisi ekle"""
session = requests.Session()

retry_strategy = Retry(  
    total=3,  
    backoff_factor=1,  
    status_forcelist=[429, 500, 502, 503, 504],  
)  
  
adapter = HTTPAdapter(max_retries=retry_strategy)  
session.mount("http://", adapter)  
session.mount("https://", adapter)  
  
return session

def is_allowed_url(url):
"""Güvenli URL kontrolü"""
try:
parsed = urlparse(url)
forbidden_netlocs = ['localhost', '127.0.0.1', '0.0.0.0', '::1', '192.168.', '10.', '172.16.']
if any(forbidden in parsed.netloc for forbidden in forbidden_netlocs):
return False
if parsed.scheme not in ('http', 'https'):
return False
return True
except:
return False

def smart_fetch(url, is_image=False):
"""Akıllı içerik getirme fonksiyonu"""
if is_image:
strategies = [
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Accept': 'image/webp,image/apng,image/,/;q=0.8',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Referer': 'https://dengetv66.live/',
'Sec-Fetch-Dest': 'image',
'Sec-Fetch-Mode': 'no-cors',
'Sec-Fetch-Site': 'cross-site',
'Cache-Control': 'no-cache'
},
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Accept': 'image/webp,image/apng,image/,/;q=0.8',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Referer': 'https://www.google.com/',
'Sec-Fetch-Dest': 'image',
'Sec-Fetch-Mode': 'no-cors',
'Sec-Fetch-Site': 'cross-site',
}
]
else:
strategies = [
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Referer': 'https://dengetv66.live/',
'Accept': '/',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Accept-Encoding': 'gzip, deflate, br',
'Origin': 'https://dengetv66.live',
'Sec-Fetch-Dest': 'empty',
'Sec-Fetch-Mode': 'cors',
'Sec-Fetch-Site': 'cross-site',
'Cache-Control': 'no-cache'
},
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Referer': 'https://mactadi2.blogspot.com/',
'Accept': '/',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Accept-Encoding': 'gzip, deflate, br',
'Origin': 'https://mactadi2.blogspot.com',
'Cache-Control': 'no-cache'
},
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Referer': 'https://www.google.com/',
'Accept': '/',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Cache-Control': 'no-cache'
},
{
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
'Accept': '/',
'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
'Cache-Control': 'no-cache'
}
]

session = create_session()  

for i, headers in enumerate(strategies):  
    try:  
        logging.info(f"Strateji {i + 1} deneniyor: {url}")  
        response = session.get(url, headers=headers, timeout=30, verify=True)  
          
        logging.info(f"Strateji {i + 1} status: {response.status_code}")  

        if response.status_code == 200:  
            logging.info(f"Strateji {i + 1} başarılı!")  
            return {  
                'content': response.content if is_image else response.text,  
                'content_type': response.headers.get('content-type', ''),  
                'status': response.status_code,  
                'headers': dict(response.headers)  
            }  
        elif response.status_code in [403, 404]:  
            logging.warning(f"Strateji {i + 1} {response.status_code} hatası, bir sonraki deneniyor...")  
            time.sleep(1)  
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
"""Ana proxy endpoint'i"""
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

    # M3U8 playlist işleme  
    if 'mpegurl' in content_type or '.m3u8' in src:  
        logging.info('M3U8 playlist tespit edildi')  

        def replace_segment(match):  
            """TS segmentlerini ve diğer dosyaları değiştir"""  
            segment_url = match.group(1)  
            if not segment_url.startswith('http'):  
                return resolve_url(segment_url, base_url_parsed)  
            return segment_url  

        def replace_img(match):  
            """Resim URL'lerini değiştir"""  
            img_url = match.group(1)  
            if not img_url.startswith('http'):  
                img_url = resolve_url(img_url, base_url_parsed)  
              
            # Cloudflare korumalı resimler için proxy kullan  
            if 'pages.dev' in img_url or 'cloudflare' in img_url:  
                return f"{request.url_root}image?src={img_url}"  
            else:  
                return img_url  

        def replace_key(match):  
            """Şifreleme anahtar URL'lerini değiştir"""  
            key_url = match.group(1)  
            if not key_url.startswith('http'):  
                key_url = resolve_url(key_url, base_url_parsed)  
            return match.group(0).replace(match.group(1), key_url)  

        # Tüm segmentleri değiştir  
        content = re.sub(r'(\S+\.ts)(?:\?[^#\s]*)?', replace_segment, content)  
        # M3U8 playlistlerini değiştir  
        content = re.sub(r'(\S+\.m3u8)(?:\?[^#\s]*)?', replace_segment, content)  
        # Resimleri değiştir  
        content = re.sub(r'(\S+\.(jpg|jpeg|png|webp|gif))(?:\?[^#\s]*)?', replace_img, content)  
        # Şifreleme anahtarlarını değiştir  
        content = re.sub(r'#EXT-X-KEY:.*URI="([^"]+)"', replace_key, content)  

        return Response(  
            content,  
            mimetype='application/vnd.apple.mpegurl',  
            headers={  
                'Cache-Control': 'no-cache, no-store, must-revalidate',  
                'Pragma': 'no-cache',  
                'Expires': '0',  
                'Content-Type': 'application/vnd.apple.mpegurl',  
                'Accept-Ranges': 'bytes',  
                'Access-Control-Allow-Origin': '*'  
            }  
        )  
    else:  
        # Diğer içerik türleri (HTML, text, vb.)  
        content_bytes = content.encode('utf-8') if isinstance(content, str) else content  
        return Response(  
            content_bytes,  
            mimetype=content_type if content_type else 'application/octet-stream',  
            headers={  
                'Content-Length': str(len(content_bytes)),  
                'Cache-Control': 'public, max-age=3600',  
                'Access-Control-Allow-Origin': '*'  
            }  
        )  

except Exception as e:  
    logging.error(f"Proxy hatası: {str(e)}\n{traceback.format_exc()}")  
    return "İç sunucu hatası", 500

@app.route('/image')
def image_proxy():
"""Resimler için özel proxy endpoint'i"""
src = request.args.get('src')
if not src:
return "Hata: 'src' parametresi gerekli.", 400

if not is_allowed_url(src):  
    return "Hata: İzin verilmeyen URL.", 400  

try:  
    logging.info(f'Resim proxy isteği: {src}')  
    result = smart_fetch(src, is_image=True)  
      
    if result:  
        return Response(  
            result['content'],  
            mimetype=result['content_type'] or 'image/jpeg',  
            headers={  
                'Cache-Control': 'public, max-age=86400',  # Resimler için daha uzun cache  
                'Access-Control-Allow-Origin': '*',  
                'Content-Type': result['content_type'] or 'image/jpeg'  
            }  
        )  
    else:  
        # Fallback: boş bir resim döndür  
        from io import BytesIO  
        from PIL import Image  
        import base64  
          
        # 1x1 piksel şeffaf PNG  
        empty_img = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')  
        return Response(  
            empty_img,  
            mimetype='image/png',  
            headers={  
                'Cache-Control': 'no-cache',  
                'Access-Control-Allow-Origin': '*'  
            }  
        )  
  
except Exception as e:  
    logging.error(f"Resim proxy hatası: {str(e)}")  
    return "Resim yüklenemedi", 404

@app.route('/clappr_proxy')
def clappr_proxy():
"""Clappr player için optimize edilmiş proxy"""
src = request.args.get('src')
if not src:
return "Hata: 'src' parametresi gerekli.", 400

if not is_allowed_url(src):  
    return "Hata: İzin verilmeyen URL.", 400  

try:  
    logging.info(f'Clappr proxy isteği: {src}')  
      
    # Clappr için özel headers  
    headers = {  
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',  
        'Accept': '*/*',  
        'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',  
        'Accept-Encoding': 'gzip, deflate, br',  
        'Referer': 'https://dengetv66.live/',  
        'Origin': 'https://dengetv66.live',  
        'Sec-Fetch-Dest': 'empty',  
        'Sec-Fetch-Mode': 'cors',  
        'Sec-Fetch-Site': 'cross-site',  
        'DNT': '1',  
        'Connection': 'keep-alive',  
    }  
      
    session = create_session()  
    response = session.get(src, headers=headers, timeout=30, verify=True)  
      
    if response.status_code == 200:  
        content_type = response.headers.get('content-type', '')  
          
        # M3U8 içeriğini işle  
        if 'mpegurl' in content_type or '.m3u8' in src:  
            content = response.text  
            base_url_parsed = urlparse(src)  
              
            # Tüm URL'leri mutlak URL'lere çevir  
            def make_absolute(match):  
                segment_url = match.group(1)  
                if not segment_url.startswith('http'):  
                    return resolve_url(segment_url, base_url_parsed)  
                return segment_url  
              
            # Tüm segment ve resim URL'lerini değiştir  
            content = re.sub(r'(\S+\.(ts|m3u8))(?:\?[^#\s]*)?', make_absolute, content)  
            content = re.sub(r'(\S+\.(jpg|jpeg|png|webp|gif))(?:\?[^#\s]*)?', make_absolute, content)  
              
            return Response(  
                content,  
                mimetype='application/vnd.apple.mpegurl',  
                headers={  
                    'Access-Control-Allow-Origin': '*',  
                    'Cache-Control': 'no-cache',  
                    'Content-Type': 'application/vnd.apple.mpegurl'  
                }  
            )  
        else:  
            return Response(  
                response.content,  
                mimetype=content_type,  
                headers={  
                    'Access-Control-Allow-Origin': '*',  
                    'Cache-Control': 'public, max-age=3600'  
                }  
            )  
    else:  
        return f"Hata: {response.status_code}", response.status_code  
          
except Exception as e:  
    logging.error(f"Clappr proxy hatası: {str(e)}")  
    return "İç sunucu hatası", 500

CORS headers

@app.after_request
def after_request(response):
response.headers['Access-Control-Allow-Origin'] = '*'
response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, HEAD'
response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Range, Accept-Encoding, X-Requested-With'
response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range, Accept-Ranges'
response.headers['Access-Control-Max-Age'] = '86400'
return response

@app.route('/', methods=['OPTIONS'])
@app.route('/image', methods=['OPTIONS'])
@app.route('/clappr_proxy', methods=['OPTIONS'])
def handle_options():
return '', 200

@app.route('/health')
def health_check():
"""Sağlık kontrol endpoint'i"""
return {'status': 'healthy', 'timestamp': time.time()}

if name == 'main':
app.run(debug=False, host='0.0.0.0', port=5000, threaded=True

