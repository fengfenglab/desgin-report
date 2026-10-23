#!/usr/bin/env python3
"""把 out/<项目>/ 打包成一个独立的 .html（双击就能在 Chrome 里打开，不需要服务器）。

用法：python3 tools/inline.py out/<项目> out/<文件名>.html [--max-mb 25]

- CSS、JS、字体、二维码直接内嵌（data URI）
- 页面图片只存一份：放在页尾的 <script type="application/json">，打开时转成 blob 地址，
  再填回 <img>/data-lb 等属性；同一张图被引用多次也不会重复占体积
- 去掉 srcset（单文件里只保留一个尺寸）
"""
import base64, json, os, re, sys, mimetypes

def data_uri(path):
    mt = mimetypes.guess_type(path)[0] or ('font/woff2' if path.endswith('.woff2') else 'application/octet-stream')
    if path.endswith('.webp'): mt = 'image/webp'
    return f'data:{mt};base64,' + base64.b64encode(open(path, 'rb').read()).decode()

def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    src, dst = a[0], a[1]
    max_mb = float(a[a.index('--max-mb') + 1]) if '--max-mb' in a else 25
    h = open(os.path.join(src, 'index.html'), encoding='utf-8').read()
    # CSS（字体内嵌）
    css = open(os.path.join(src, 'assets', 'style.css'), encoding='utf-8').read()
    css = re.sub(r'url\(([^)"\']+\.woff2)\)', lambda m: 'url(' + data_uri(os.path.join(src, 'assets', m.group(1))) + ')', css)
    h = re.sub(r'<link rel="preload"[^>]*>', '', h)
    h = re.sub(r'<link rel="stylesheet" href="assets/style\.css(\?v=\w+)?">', lambda m: '<link rel="stylesheet" href="assets/style.css">', h)
    h = h.replace('<link rel="stylesheet" href="assets/style.css">', '<style>' + css.replace('</style', '<\\/style') + '</style>')
    # 其他 assets（二维码、logo 等）
    h = re.sub(r'assets/([A-Za-z0-9_.-]+\.(?:png|jpe?g|webp|svg|gif))', lambda m: data_uri(os.path.join(src, 'assets', m.group(1))), h)
    # 图片：src → data-xs，其余属性里的 img/xxx → xf:xxx，打开时替换成 blob 地址
    h = re.sub(r'\s(?:srcset|sizes)="[^"]*"', '', h)
    h = re.sub(r'(<img\b[^>]*?)\ssrc="img/([A-Za-z0-9_.-]+)"', r'\1 data-xs="\2"', h)
    used = sorted(set(re.findall(r'img/([A-Za-z0-9_.-]+)', h)) | set(re.findall(r'data-xs="([^"]+)"', h)))
    h = re.sub(r'img/([A-Za-z0-9_.-]+)', r'xf:\1', h)
    blob = {k: base64.b64encode(open(os.path.join(src, 'img', k), 'rb').read()).decode() for k in used}
    boot = ('<script>(function(){var D=JSON.parse(document.getElementById("xf-img").textContent),U={};'
            'function u(k){if(!U[k]){var b=atob(D[k]),n=b.length,a=new Uint8Array(n);for(var i=0;i<n;i++)a[i]=b.charCodeAt(i);'
            'U[k]=URL.createObjectURL(new Blob([a],{type:"image/webp"}));}return U[k];}'
            'var all=document.querySelectorAll("*");for(var i=0;i<all.length;i++){var el=all[i],at=el.attributes;'
            'for(var j=0;j<at.length;j++){var v=at[j].value;if(v.indexOf("xf:")>-1)el.setAttribute(at[j].name,v.replace(/xf:([A-Za-z0-9_.-]+)/g,function(_,k){return D[k]?u(k):_;}));}'
            'var s=el.getAttribute("data-xs");if(s&&D[s])el.src=u(s);}})();</script>')
    data = '<script type="application/json" id="xf-img">' + json.dumps(blob) + '</script>'
    js = open(os.path.join(src, 'assets', 'app.js'), encoding='utf-8').read().replace('</script', '<\\/script')
    h = re.sub(r'<script src="assets/app\.js(\?v=\w+)?" defer></script>', '', h)
    h = h.replace('</body>', data + boot + '<script>' + js + '</script></body>')
    left = re.findall(r'(?:src|href)="(?!data:|#|http|xf:|javascript)[^"]+"', h)
    if left: print('提示：还有外部引用', left[:5])
    open(dst, 'w', encoding='utf-8').write(h)
    mb = os.path.getsize(dst) / 1e6
    print(f'完成 → {dst}  {mb:.1f} MB，{len(used)} 张图')
    if mb > max_mb: print(f'警告：超过 {max_mb} MB')

if __name__ == '__main__': main()
