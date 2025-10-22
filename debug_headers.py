#!/usr/bin/env python3
"""
Diagnóstico rápido: verifica qué headers está recibiendo Flask desde NPM.
Ejecuta en el VPS dentro del contenedor para debuggear.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, request

app = Flask(__name__)

# Apply ProxyFix to see the actual headers
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

@app.route('/debug/headers')
def debug_headers():
    """Endpoint que muestra todos los headers recibidos."""
    headers_dict = {
        key: value for key, value in request.headers
    }
    
    info = {
        "remote_addr": request.remote_addr,
        "scheme": request.scheme,
        "host": request.host,
        "path": request.path,
        "method": request.method,
        "all_headers": headers_dict,
        # Específicos para proxy
        "x_forwarded_for": request.headers.get('X-Forwarded-For'),
        "x_forwarded_proto": request.headers.get('X-Forwarded-Proto'),
        "x_forwarded_host": request.headers.get('X-Forwarded-Host'),
        "x_forwarded_port": request.headers.get('X-Forwarded-Port'),
        "x_real_ip": request.headers.get('X-Real-IP'),
    }
    
    return info, 200, {"Content-Type": "application/json"}

if __name__ == '__main__':
    print("=" * 80)
    print("DIAGNÓSTICO DE HEADERS - DEBUG ENDPOINT")
    print("=" * 80)
    print(f"Ejecuta desde el VPS (o cliente):")
    print(f"  curl http://51.79.49.242:8087/debug/headers")
    print(f"O desde la página de NPM:")
    print(f"  curl https://tesis.brosdev.duckdns.org/debug/headers")
    print("=" * 80)
    app.run(host='0.0.0.0', port=5001, debug=True)
