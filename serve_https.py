import os
import importlib.util


def load_app_module():
    base = os.path.dirname(os.path.abspath(__file__))
    app_py = os.path.join(base, 'app.py')
    spec = importlib.util.spec_from_file_location('app_module', app_py)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load app.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == '__main__':
    # Use waitress-serve which supports SSL via command line
    mod = load_app_module()
    host = os.environ.get('HOST', '0.0.0.0')
    try:
        port = int(os.environ.get('PORT', '5443'))
    except Exception:
        port = 5443

    certfile = os.environ.get('SSL_CERTFILE')
    keyfile = os.environ.get('SSL_KEYFILE')
    if not (certfile and keyfile and os.path.exists(certfile) and os.path.exists(keyfile)):
        raise SystemExit('For HTTPS set SSL_CERTFILE and SSL_KEYFILE to valid paths')

    # We invoke waitress-serve through os.exec* to pass SSL params
    cmd = [
        'waitress-serve',
        f'--host={host}',
        f'--port={port}',
        f'--url-scheme=https',
        f'--ssl-certfile={certfile}',
        f'--ssl-keyfile={keyfile}',
        'app:app'
    ]
    os.execvp(cmd[0], cmd)


