import requests
urls = [
    'https://raw.githubusercontent.com/khadaj/np-local-levels/master/local-levels.json',
    'https://raw.githubusercontent.com/np-nepal/nepal-datasets/master/data/local-levels.json',
    'https://raw.githubusercontent.com/ashish/geojson-nepal/master/data/local-levels.json',
]
for url in urls:
    try:
        r = requests.get(url, timeout=20)
        print(url, r.status_code, r.text[:200])
    except Exception as exc:
        print(url, 'ERR', exc)
