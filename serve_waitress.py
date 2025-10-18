import importlib.util
import os
from waitress import serve


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
    mod = load_app_module()
    host = os.environ.get('HOST', '127.0.0.1')
    try:
        port = int(os.environ.get('PORT', '5051'))
    except Exception:
        port = 5051
    print(f"[waitress] Starting on http://{host}:{port} (CTRL+C to stop)")
    # در صورت تنظیم فایل‌های گواهی، waitress-sslify ساده: برای محیط ویندوز بهتری است با waitress-serve
    certfile = os.environ.get('SSL_CERTFILE')
    keyfile = os.environ.get('SSL_KEYFILE')
    if certfile and keyfile:
        print('[waitress] HTTPS requested via SSL_CERTFILE/SSL_KEYFILE but built-in waitress.serve has no SSL. Use run_webhook_https.bat with waitress-serve.')
    try:
        serve(mod.app, host=host, port=port)
    except Exception as exc:
        print(f"[waitress] Failed to start: {exc}")


