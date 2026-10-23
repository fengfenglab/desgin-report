#!/usr/bin/env python3
"""截图工具：python tools/shoot_pages.py <out 下的目录> <页码,页码…> [前缀]  → shots/<前缀>-pNN.png（手机 390x844）。
页码后加 t 表示同时截「目录浮层」，例如 1,2,toc。"""
import os, sys, http.server, functools, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d, pages = sys.argv[1], sys.argv[2].split(','); pre = sys.argv[3] if len(sys.argv) > 3 else d
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *x): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'out')))
threading.Thread(target=srv.serve_forever, daemon=True).start()
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport=dict(width=390, height=844), device_scale_factor=3, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    pg.on('pageerror', lambda x: errs.append(str(x)))
    pg.goto(f'http://127.0.0.1:{srv.server_port}/{d}/', wait_until='networkidle')
    pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(700)
    for k in pages:
        k = int(k)
        pg.evaluate(f'document.querySelectorAll(".pg")[{k-1}].scrollIntoView()')
        pg.evaluate(f'''Promise.all([...document.querySelectorAll(".pg")[{k-1}].querySelectorAll("img")].map(i=>{{i.loading="eager";return i.complete?1:new Promise(r=>{{i.onload=i.onerror=r}})}}))''')
        pg.wait_for_timeout(1000)
        pg.screenshot(path=os.path.join(ROOT, 'shots', f'{pre}-p{k:02d}.png'))
    b.close()
print(d, 'ERRORS:', errs or 'none')
