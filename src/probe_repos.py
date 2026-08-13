import subprocess
repos = [
    'https://github.com/khadaj/np-local-levels.git',
    'https://github.com/np-nepal/nepal-datasets.git',
    'https://github.com/ashish/geojson-nepal.git',
]
for repo in repos:
    try:
        out = subprocess.check_output(['git', 'ls-remote', repo], stderr=subprocess.STDOUT, timeout=20).decode('utf-8', 'ignore')
        print(repo, 'OK', out.splitlines()[:2])
    except Exception as exc:
        print(repo, 'ERR', exc)
