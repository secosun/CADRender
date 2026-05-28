import json
import urllib.request

url = 'http://127.0.0.1:8099/v1/messages?beta=true'
req = urllib.request.Request(url, method='POST')
req.add_header('x-api-key', 'sk-0b5aa6c7ed894bd49ab03d8975593846')
req.add_header('Content-Type', 'application/json')
body = {
    'model': 'claude-sonnet-4-6',
    'messages': [
        {
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'media_type': 'image/png',
                        'data': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEklEQVR42mP8z8AARwAI/AL+vTggAAAAAElFTkSuQmCC'
                    }
                }
            ]
        }
    ]
}

data = json.dumps(body, ensure_ascii=False).encode('utf-8')
try:
    with urllib.request.urlopen(req, data=data) as r:
        print('STATUS', r.status)
        print(r.read().decode('utf-8', errors='replace'))
except urllib.error.HTTPError as e:
    print('STATUS', e.code)
    print(e.read().decode('utf-8', errors='replace'))
except Exception as e:
    print('ERROR', e)
