def create_app():
    # برگشت همان app موجود تا زمانی که روت‌ها کاملاً به بلوپرینت منتقل شوند
    from run import app as _app
    return _app


