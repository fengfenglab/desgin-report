#!/usr/bin/env python3
"""跨设备「图片不裁切」检查：python tools/nocrop.py <网址或 out/<项目>> [--shots 页码,页码] [--only 设备名]
设备：iPhone WebKit（390×844、390×664 微信）、安卓 Chromium（微信 XWEB UA、华为浏览器 UA；360×780 / 393×851 / 412×915 / 360×640）。
逐页逐图比较：图片原始比例 vs 实际显示内容（含 object-fit:cover 裁切、祖先 overflow 裁切）。
满版背景（封面 cover / 章节 section / 结尾 about 页的背景图）按设计允许裁切，单独列出不算错。
退出码：有裁切 = 1。截图存 shots/nocrop-<设备>-pNN.png。"""
import os, sys, argparse, http.server, functools, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.47(0x18002f2f) NetType/WIFI Language/zh_CN'
WX_AND = 'Mozilla/5.0 (Linux; Android 12; NOH-AN00 Build/HUAWEINOH-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/111.0.5563.116 Mobile Safari/537.36 XWEB/1110001 MMWEBSDK/20231202 MMWEBID/1234 MicroMessenger/8.0.47.2560(0x28002F35) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64'
HW = 'Mozilla/5.0 (Linux; Android 12; HarmonyOS; NOH-AN00; HMSCore 6.13.0.302) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.196 HuaweiBrowser/15.0.4.312 Mobile Safari/537.36'
DEVICES = [('ios-844', 'webkit', IOS, 390, 844), ('ios-wx-664', 'webkit', IOS, 390, 664),
           ('hw-360x780', 'chromium', HW, 360, 780), ('wx-393x851', 'chromium', WX_AND, 393, 851),
           ('hw-412x915', 'chromium', HW, 412, 915), ('wx-360x640', 'chromium', WX_AND, 360, 640)]
JS = r"""()=>{const out=[];const secs=[...document.querySelectorAll('section.pg')];
secs.forEach((s,i)=>s.querySelectorAll('img').forEach(im=>{
  const r=im.getBoundingClientRect(); if(!r.width||!r.height||!im.naturalWidth) return;
  const cs=getComputedStyle(im); if(cs.visibility=='hidden'||+cs.opacity===0&&!im.classList.contains('ok')&&im.complete===false) return;
  const k=s.classList; const bg=k.contains('cover')||k.contains('section')||k.contains('about');
  const pl=parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight), pt=parseFloat(cs.paddingTop)+parseFloat(cs.paddingBottom);
  const bw=r.width-pl, bh=r.height-pt, na=im.naturalWidth/im.naturalHeight, ba=bw/bh;
  let fit=cs.objectFit, crop=0;
  if(fit=='cover'||fit=='fill'&&Math.abs(na-ba)/na>.02) crop=Math.abs(na-ba)/Math.max(na,ba);
  // 祖先裁切（横向 swipe 轨道里完全在外面的幻灯片跳过）
  let x0=r.left,y0=r.top,x1=r.right,y1=r.bottom;
  for(let a=im.parentElement;a&&a!==document.body;a=a.parentElement){const c=getComputedStyle(a);
    if(c.overflowX!='visible'||c.overflowY!='visible'){const q=a.getBoundingClientRect();
      const nx0=c.overflowX!='visible'?Math.max(x0,q.left):x0, nx1=c.overflowX!='visible'?Math.min(x1,q.right):x1;
      const ny0=c.overflowY!='visible'&&c.overflowY!='auto'&&c.overflowY!='scroll'?Math.max(y0,q.top):y0, ny1=c.overflowY!='visible'&&c.overflowY!='auto'&&c.overflowY!='scroll'?Math.min(y1,q.bottom):y1;
      x0=nx0;x1=nx1;y0=ny0;y1=ny1;}}
  const vis=Math.max(0,x1-x0)*Math.max(0,y1-y0)/(r.width*r.height);
  if(vis===0) return;               // 不在可视轨道上（另一张幻灯片）
  const clip=1-vis;
  if(crop>.02||clip>.02) out.push({p:i+1,t:s.className.replace('pg ',''),src:(im.currentSrc||im.src).split('/').pop(),fit,crop:+crop.toFixed(3),clip:+clip.toFixed(3),bg});
}));return {n:secs.length,bad:out};}"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('target'); ap.add_argument('--shots', default=''); ap.add_argument('--only', default='')
    a = ap.parse_args(); url = a.target
    if not url.startswith('http'):
        d = os.path.abspath(url)
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(type('Q', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *x: None}), directory=os.path.dirname(d)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{srv.server_port}/{os.path.basename(d)}/'
    fails = 0
    with sync_playwright() as p:
        for name, eng, ua, w, h in DEVICES:
            if a.only and a.only not in name: continue
            b = (p.webkit.launch() if eng == 'webkit' else p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox']))
            ctx = b.new_context(viewport=dict(width=w, height=h), device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=ua)
            pg = ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(url, wait_until='networkidle'); pg.wait_for_timeout(600)
            n = pg.evaluate("document.querySelectorAll('section.pg').length")
            bad = []
            for i in range(n):   # 每页滚到可视位置、等懒加载，再测
                pg.evaluate(f"document.querySelectorAll('section.pg')[{i}].scrollIntoView()"); pg.wait_for_timeout(250)
                r = pg.evaluate(JS)
                bad += [x for x in r['bad'] if x['p'] == i + 1]
            real = [x for x in bad if not x['bg']]; bgs = [x for x in bad if x['bg']]
            print(f'[{name}] {eng} {w}x{h}: pages {n}, cropped {len(real)}, full-bleed bg (allowed) {len(bgs)}, js errors {len(errs)}')
            for x in real: print('   CROP', x)
            fails += len(real) + len(errs)
            for k in [s for s in a.shots.split(',') if s]:
                pg.evaluate(f"document.querySelectorAll('section.pg')[{int(k)-1}].scrollIntoView()"); pg.wait_for_timeout(1200)
                pg.screenshot(path=os.path.join(ROOT, 'shots', f'nocrop-{name}-p{int(k):02d}.png'))
            b.close()
    print('RESULT:', 'OK no cropping' if not fails else f'{fails} problems'); sys.exit(1 if fails else 0)

main()
