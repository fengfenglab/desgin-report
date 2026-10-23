#!/usr/bin/env python3
"""用 Playwright + 本机 Chrome 检查网页：手机 390x844 与桌面 1280x800 截图，并报告控制台错误/空白页。
用法: <venv>/bin/python tools/shoot.py out/my-project [--pages 1,3,5] [--url http://...]"""
import argparse, os, sys, http.server, threading, functools
from playwright.sync_api import sync_playwright
ap = argparse.ArgumentParser(); ap.add_argument('site'); ap.add_argument('--pages', default='1,2,3,4,5,10,11,16,32,36,37')
ap.add_argument('--url'); ap.add_argument('--shots', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shots'))
a = ap.parse_args()
os.makedirs(a.shots, exist_ok=True)
url = a.url
if not url:
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x): pass
    h = functools.partial(Q, directory=a.site)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_port}/'
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for name, vp, mobile in (('mobile', dict(width=390, height=844), True), ('desktop', dict(width=1280, height=800), False)):
        ctx = b.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile,
                            user_agent=('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50' if mobile else None))
        pg = ctx.new_page()
        pg.on('console', lambda m, n=name: m.type == 'error' and errs.append(f'{n}: console {m.text}'))
        pg.on('pageerror', lambda ex, n=name: errs.append(f'{n}: pageerror {ex}'))
        pg.on('requestfailed', lambda r, n=name: errs.append(f'{n}: requestfailed {r.url}'))
        pg.goto(url, wait_until='networkidle')
        n = pg.evaluate('document.querySelectorAll(".pg").length')
        print(name, 'pages:', n, 'body text len:', pg.evaluate('document.body.innerText.length'))
        for k in [int(x) for x in a.pages.split(',') if int(x) <= n]:
            pg.evaluate(f'document.querySelectorAll(".pg")[{k-1}].scrollIntoView()')
            pg.wait_for_timeout(250)
            pg.evaluate(f'''Promise.all([...document.querySelectorAll(".pg")[{k-1}].querySelectorAll("img")].map(i=>{{i.loading="eager";return i.complete?1:new Promise(r=>{{i.onload=i.onerror=r}})}}))''')
            pg.wait_for_timeout(700)
            info = pg.evaluate(f'''(()=>{{const s=document.querySelectorAll(".pg")[{k-1}];const r=s.getBoundingClientRect();
              const imgs=[...s.querySelectorAll("img")];return {{h:Math.round(r.height),imgs:imgs.length,broken:imgs.filter(i=>!i.naturalWidth).length,txt:s.innerText.trim().length}}}})()''')
            if info['broken']: errs.append(f'{name}: page {k} broken images {info["broken"]}')
            print(f'  p{k:02d}', info)
            pg.screenshot(path=os.path.join(a.shots, f'{name}-p{k:02d}.png'))
        ctx.close()
    b.close()
print('ERRORS:', errs if errs else 'none')
