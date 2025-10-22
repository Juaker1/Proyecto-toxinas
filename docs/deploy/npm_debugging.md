# Diagnóstico: NPM + Flask no carga página

## Síntomas
- `curl -I http://51.79.49.242:8087/` devuelve 200 OK con HTML correcto (18074 bytes)
- NPM está configurado: Forward a http://51.79.49.242:8087
- Página se queda en blanco o carga indefinidamente cuando accedes vía `https://tesis.brosdev.duckdns.org`

## Causas comunes

### 1) **NPM no pasa X-Forwarded-* headers**
NPM puede estar omitiendo headers que Flask necesita para generar URLs correctas con HTTPS.

**Solución:**
1. En NPM, edita el Proxy Host `tesis.brosdev.duckdns.org`
2. Ve a la pestaña **Advanced**
3. Añade en el campo "Custom Nginx Configuration":
   ```nginx
   proxy_set_header X-Forwarded-For $remote_addr;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Forwarded-Host $server_name;
   proxy_set_header X-Forwarded-Port $server_port;
   proxy_set_header X-Real-IP $remote_addr;
   ```
4. Guarda

### 2) **Cache del navegador**
Algunos navegadores cachean respuestas vacías o incompletas.

**Solución:**
- Abre DevTools (F12)
- Ve a Settings > Network
- Marca "Disable cache"
- Recarga la página (Ctrl+Shift+R)

### 3) **Archivos estáticos no se cargan**
Si el HTML se sirve pero CSS/JS no, NPM puede estar bloqueando rutas `/static`.

**Solución en NPM:**
- En la pestaña **Custom locations**, asegúrate de que no hay reglas que bloqueen `/static` o `/assets`

### 4) **DEBUG mode debe estar ON para diagnosticar**
En la versión Docker, establecí `DEBUG=1` en el compose para que Flask tenga logs más verbosos.

**Verificar logs:**
```powershell
# En el VPS
docker logs -f toxinas_app
```

Busca errores como:
- `TemplateNotFound`
- `Connection refused`
- `Permission denied`

## Pasos de diagnóstico inmediatos

1. **Reinicia el contenedor con DEBUG=1:**
   ```powershell
   docker compose up -d app
   docker logs -f toxinas_app
   ```
   Espera 30s y observa si hay errores.

2. **Prueba desde el VPS (sin NPM):**
   ```powershell
   curl http://51.79.49.242:8087/ | head -50
   ```
   Verifica que el HTML tenga `<html>`, `<head>`, `<body>`, etc.

3. **Prueba rutas de recursos:**
   ```powershell
   curl -I http://51.79.49.242:8087/static/css/main.css
   curl -I http://51.79.49.242:8087/static/js/app.js
   ```
   Deben devolver 200 OK.

4. **Desde tu navegador local**, abre la consola (F12) y mira:
   - Network tab: ¿qué peticiones fallan? ¿cuál es el status?
   - Console tab: ¿hay errores JavaScript?

## Recomendación rápida

Si tras estos pasos sigue sin cargar, te sugiero:
1. Desactiva el SSL en NPM temporalmente (usar http en lugar de https) para descartar que sea un problema de esquema.
2. Prueba accediendo directamente por IP desde local: `http://51.79.49.242:8087`
3. Compara el HTML que baja por NPM vs. directamente por IP.

Si el HTML difiere, el problema está en NPM. Si es igual pero la página sigue en blanco, el problema es JavaScript (assets que no cargan o rutas relativas rotas).
