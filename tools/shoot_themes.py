#!/usr/bin/env python3
"""四套风格样张：每套截封面 + 一张内页（手机 390x844），并拼成对比图。
用法: <venv>/bin/python tools/shoot_themes.py [--page 24] [--themes zen,wabi,mono,french]"""
import argparse, os, http.server, functools, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--page', type=int, default=24); ap.add_argument('--themes', default='zen,wabi,mono,french')
a = ap.parse_args()
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *x): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=os.path.join(ROOT, 'out')))
threading.Thread(target=srv.serve_forever, daemon=True).start()
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for t in a.themes.split(','):
        ctx = b.new_context(viewport=dict(width=390, height=844), device_scale_factor=3, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on('console', lambda m, t=t: m.type == 'error' and errs.append(f'{t}: {m.text}'))
        pg.on('pageerror', lambda x, t=t: errs.append(f'{t}: {x}'))
        pg.goto(f'http://127.0.0.1:{srv.server_port}/theme-{t}/', wait_until='networkidle')
        pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(900)
        for k, name in ((1, 'cover'), (a.page, f'p{a.page:02d}')):
            pg.evaluate(f'document.querySelectorAll(".pg")[{k-1}].scrollIntoView()')
            pg.evaluate(f'''Promise.all([...document.querySelectorAll(".pg")[{k-1}].querySelectorAll("img")].map(i=>{{i.loading="eager";return i.complete?1:new Promise(r=>{{i.onload=i.onerror=r}})}}))''')
            pg.wait_for_timeout(1200)
            pg.screenshot(path=os.path.join(ROOT, 'shots', f'theme-{t}-{name}.png'))
        ctx.close()
    b.close()
print('ERRORS:', errs or 'none')
