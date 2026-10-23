/* 汇报网页交互（原创，无依赖） */
(function(){
'use strict';
var D=document,W=window,body=D.body;
var pages=[].slice.call(D.querySelectorAll('.pg'));
var N=pages.length,cur=0;
var numEl=D.getElementById('num'),chapEl=D.getElementById('chap'),progEl=D.getElementById('prog');

/* 视口高度（兼容不支持 svh 的微信内核），只在宽度变化时更新，避免地址栏伸缩抖动 */
var lastW=0;
function setVh(){if(W.innerWidth!==lastW){lastW=W.innerWidth;D.documentElement.style.setProperty('--vh',W.innerHeight*0.01+'px');}}
setVh();W.addEventListener('resize',setVh);

/* 图片淡入 */
function ok(img){img.classList.add('ok');}
[].forEach.call(D.querySelectorAll('.ph img'),function(img){
  if(img.complete&&img.naturalWidth)ok(img);else{img.addEventListener('load',function(){ok(img);});img.addEventListener('error',function(){ok(img);});}
});

/* 当前页：页码、章节、进度条、深色页反色 */
function setCur(i){
  cur=i;var p=pages[i];
  numEl.innerHTML=pad(i+1)+'<i>/'+pad(N)+'</i>';
  chapEl.textContent=p.getAttribute('data-chap')||'';
  progEl.style.width=((i+1)/N*100)+'%';
  body.classList.toggle('on-dark',p.hasAttribute('data-dark'));
  body.classList.toggle('on-cover',i===0);
  body.classList.toggle('on-darkbot',p.hasAttribute('data-darkbot'));
  var ci=p.getAttribute('data-ci');[].forEach.call(D.querySelectorAll('#dots button'),function(b){b.classList.toggle('on',b.getAttribute('data-ci')===ci);});
  if(history.replaceState)history.replaceState(null,'',i?'#p'+(i+1):location.pathname+location.search);
  /* 预加载下一页图片 */
  var nx=pages[i+1];if(nx)[].forEach.call(nx.querySelectorAll('img[loading=lazy]'),function(im){im.loading='eager';});
}
function pad(n){return n<10?'0'+n:''+n;}
if('IntersectionObserver' in W){
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)setCur(pages.indexOf(e.target));});},{threshold:0.55});
  pages.forEach(function(p){io.observe(p);});
}else{W.addEventListener('scroll',function(){var h=W.innerHeight;setCur(Math.min(N-1,Math.round(W.scrollY/h)));});}
function go(i){i=Math.max(0,Math.min(N-1,i));pages[i].scrollIntoView({behavior:'smooth',block:'start'});}
var m=/^#p(\d+)$/.exec(location.hash);
if(m){var t=+m[1]-1;setTimeout(function(){pages[Math.min(N-1,t)].scrollIntoView();},60);}else setCur(0);

/* 键盘 / 桌面按钮 */
D.addEventListener('keydown',function(e){
  if(lb.classList.contains('open')){if(e.key==='Escape')closeLb();if(e.key==='ArrowRight')step(1);if(e.key==='ArrowLeft')step(-1);return;}
  if(['ArrowDown','PageDown',' '].indexOf(e.key)>=0){e.preventDefault();go(cur+1);}
  if(['ArrowUp','PageUp'].indexOf(e.key)>=0){e.preventDefault();go(cur-1);}
  if(e.key==='Home')go(0);if(e.key==='End')go(N-1);
});
D.getElementById('up').onclick=function(){go(cur-1);};
D.getElementById('down').onclick=function(){go(cur+1);};
[].forEach.call(D.querySelectorAll('[data-go]'),function(b){b.onclick=function(e){e.stopPropagation();if(body.classList.contains('edit')&&b.classList.contains('rdot'))return;go(+b.getAttribute('data-go'));};});

/* 平面图编号：没有对应页面的房间，点一下在图上高亮 */
[].forEach.call(D.querySelectorAll('[data-room]'),function(b){b.onclick=function(){
  var pg=b.closest('.pg'),n=b.getAttribute('data-room');
  [].forEach.call(pg.querySelectorAll('.rdot'),function(d){d.classList.toggle('hi',d.getAttribute('data-n')===n);});
  [].forEach.call(pg.querySelectorAll('[data-room]'),function(x){x.classList.toggle('on',x===b);});
};});

/* 单页内左右滑动（功能分区 / 动线视线收纳 / 方案对比 / 剖面）：原生横向滚动 + 吸附，标签和圆点跟随 */
[].forEach.call(D.querySelectorAll('.swipe'),function(pg){
  var tr=pg.querySelector('.swtrack'),tabs=pg.querySelectorAll('.swtabs button'),dots=pg.querySelectorAll('.swdots i'),cur=0,raf=0;
  function mark(k){if(k===cur)return;cur=k;
    [].forEach.call(tabs,function(b,j){b.classList.toggle('on',j===k);});
    [].forEach.call(dots,function(d,j){d.classList.toggle('on',j===k);});
    var t=tabs[k];if(t&&t.scrollIntoView){var bar=t.parentNode;bar.scrollTo({left:t.offsetLeft-(bar.clientWidth-t.offsetWidth)/2,behavior:'smooth'});}}
  tr.addEventListener('scroll',function(){if(raf)return;raf=requestAnimationFrame(function(){raf=0;mark(Math.round(tr.scrollLeft/Math.max(1,tr.clientWidth)));});},{passive:true});
  [].forEach.call(tabs,function(b,j){b.onclick=function(e){e.stopPropagation();tr.scrollTo({left:j*tr.clientWidth,behavior:'smooth'});};});
  [].forEach.call(dots,function(d,j){d.onclick=function(){tr.scrollTo({left:j*tr.clientWidth,behavior:'smooth'});};});
});

/* 目录 */
var toc=D.getElementById('toc');
D.getElementById('tocbtn').onclick=function(){toc.classList.add('open');};
toc.querySelector('.x').onclick=function(){toc.classList.remove('open');};
[].forEach.call(toc.querySelectorAll('li'),function(li){li.onclick=function(){toc.classList.remove('open');var i=+li.getAttribute('data-i');setTimeout(function(){pages[i].scrollIntoView();},300);};});

/* 看大图：左右滑切换，双指 / 双击放大，拖动平移 */
var lb=D.getElementById('lb'),stage=lb.querySelector('.stage'),lbImg=stage.querySelector('img'),
    lbCount=lb.querySelector('.lbcount'),lbCap=lb.querySelector('.lbcap'),lbTip=lb.querySelector('.lbtip');
var list=[],li=0,s=1,x=0,y=0,base=null;
function apply(){lbImg.style.transform='translate('+x+'px,'+y+'px) scale('+s+')';}
function fit(){
  lbImg.style.cssText='';s=1;var r=lbImg.getBoundingClientRect();if(!r.width)return;
  var sr=stage.getBoundingClientRect();base={w:r.width,h:r.height};x=r.left-sr.left;y=r.top-sr.top;lbImg.style.width=r.width+'px';lbImg.style.height=r.height+'px';lbImg.style.maxWidth='none';lbImg.style.maxHeight='none';lbImg.style.position='absolute';lbImg.style.left='0';lbImg.style.top='0';apply();
}
function show(i){
  li=(i+list.length)%list.length;var it=list[li];
  lbImg.style.cssText='';base=null;
  lbImg.onload=function(){fit();};lbImg.src=it.src;
  if(lbImg.complete&&lbImg.naturalWidth)setTimeout(fit,0);
  lbCount.textContent=list.length>1?(li+1)+' / '+list.length:'';
  lbCap.textContent=it.cap||'';
  lbTip.textContent=it.plan?'双指放大 · 拖动查看细节':(list.length>1?'左右滑动切换 · 双击放大':'双击放大');
}
function openLb(group,i){list=group;lb.classList.add('open');show(i);}
function closeLb(){lb.classList.remove('open');lbImg.removeAttribute('src');}
function step(d){if(list.length>1)show(li+d);}
lb.querySelector('.close').onclick=closeLb;
lb.querySelector('.prev').onclick=function(e){e.stopPropagation();step(-1);};
lb.querySelector('.next').onclick=function(e){e.stopPropagation();step(1);};
[].forEach.call(D.querySelectorAll('[data-lb]'),function(el){
  el.addEventListener('click',function(){
    if(el.hasAttribute('data-solo')){openLb([{src:el.getAttribute('data-lb'),cap:el.getAttribute('data-cap')||'',plan:true}],0);return;}
    var pg=el.closest('.pg'),els=[].slice.call(pg.querySelectorAll('[data-lb]:not([data-solo])'));
    var g=els.map(function(e){return{src:e.getAttribute('data-lb'),cap:e.getAttribute('data-cap')||'',plan:e.hasAttribute('data-plan')};});
    if(pg.hasAttribute('data-extra'))JSON.parse(pg.getAttribute('data-extra')).forEach(function(o){g.push(o);});
    openLb(g,els.indexOf(el));
  });
});
function zoomAt(ns,cx,cy){ns=Math.max(1,Math.min(6,ns));x=cx-(cx-x)*ns/s;y=cy-(cy-y)*ns/s;s=ns;clamp();apply();}
function clamp(){
  if(!base)return;var w=base.w*s,h=base.h*s,vw=stage.clientWidth,vh=stage.clientHeight;
  x=w<=vw?(vw-w)/2:Math.min(0,Math.max(vw-w,x));y=h<=vh?(vh-h)/2:Math.min(0,Math.max(vh-h,y));
}
var pts={},start=null,lastTap=0,moved=false;
stage.addEventListener('pointerdown',function(e){
  stage.setPointerCapture&&stage.setPointerCapture(e.pointerId);pts[e.pointerId]={x:e.clientX,y:e.clientY};moved=false;
  var k=Object.keys(pts);
  if(k.length===1)start={x:e.clientX,y:e.clientY,ox:x,oy:y,t:Date.now()};
  if(k.length===2){var a=pts[k[0]],b=pts[k[1]];start={d:Math.hypot(a.x-b.x,a.y-b.y),s:s,cx:(a.x+b.x)/2,cy:(a.y+b.y)/2,ox:x,oy:y};}
});
stage.addEventListener('pointermove',function(e){
  if(!pts[e.pointerId]||!start)return;pts[e.pointerId]={x:e.clientX,y:e.clientY};var k=Object.keys(pts);
  if(k.length===2&&start.d){var a=pts[k[0]],b=pts[k[1]],d=Math.hypot(a.x-b.x,a.y-b.y),cx=(a.x+b.x)/2,cy=(a.y+b.y)/2;
    var ns=Math.max(1,Math.min(6,start.s*d/start.d));x=cx-(start.cx-start.ox)*ns/start.s;y=cy-(start.cy-start.oy)*ns/start.s;s=ns;clamp();apply();moved=true;}
  else if(k.length===1&&start.ox!==undefined){var dx=e.clientX-start.x,dy=e.clientY-start.y;if(Math.abs(dx)+Math.abs(dy)>6)moved=true;
    if(s>1.01){x=start.ox+dx;y=start.oy+dy;clamp();apply();}}
});
function up(e){
  var k=Object.keys(pts),single=k.length===1;delete pts[e.pointerId];
  if(single&&start&&start.ox!==undefined){
    var dx=e.clientX-start.x,dy=e.clientY-start.y,dt=Date.now()-start.t;
    if(s<=1.01&&Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3&&dt<700){step(dx<0?1:-1);}
    else if(s<=1.01&&dy>90&&Math.abs(dy)>Math.abs(dx)*1.5){closeLb();}
    else if(!moved){var now=Date.now();if(now-lastTap<300){zoomAt(s>1.5?1:2.5,e.clientX,e.clientY);lastTap=0;}else lastTap=now;}
  }
  if(Object.keys(pts).length===0)start=null;
  else{var r=pts[Object.keys(pts)[0]];start={x:r.x,y:r.y,ox:x,oy:y,t:Date.now()};}
}
stage.addEventListener('pointerup',up);stage.addEventListener('pointercancel',up);
stage.addEventListener('wheel',function(e){e.preventDefault();zoomAt(s*(e.deltaY<0?1.15:1/1.15),e.clientX,e.clientY);},{passive:false});
W.addEventListener('resize',function(){if(lb.classList.contains('open'))fit();});

/* 坐标模式：网址后加 ?edit 打开。点平面图 → 显示该点的 x / y（占图片宽高的百分比），抄进 config 的 rooms 即可。
   估计的位置（rooms 里 "check": true）显示为虚线圈。这个模式不会出现在正常链接里。 */
if(/[?&#]edit\b/.test(location.search+location.hash)){
  body.classList.add('edit');body.classList.remove('protect');
  var tip=D.createElement('div');tip.className='edtip';tip.textContent='坐标模式：点平面图读取位置';body.appendChild(tip);
  [].forEach.call(D.querySelectorAll('.plan .pframe'),function(f){
    f.addEventListener('click',function(e){
      e.stopPropagation();e.preventDefault();
      var r=f.getBoundingClientRect(),x=(e.clientX-r.left-8)/(r.width-16)*100,y=(e.clientY-r.top-8)/(r.height-16)*100;
      x=Math.round(Math.max(0,Math.min(100,x))*10)/10;y=Math.round(Math.max(0,Math.min(100,y))*10)/10;
      var m=f.querySelector('.edmark');if(!m){m=D.createElement('i');m.className='edmark';f.appendChild(m);}
      m.style.left='calc(8px + (100% - 16px) * '+x+' / 100)';m.style.top='calc(8px + (100% - 16px) * '+y+' / 100)';
      var pg=f.closest('.pg'),sl=pg.getAttribute('data-slide');
      tip.textContent='PPT 第 '+sl+' 页   "x": '+x+', "y": '+y;
      console.log('[坐标] slide',sl,JSON.stringify({x:x,y:y}));
    },true);
  });
}

/* 轻度内容保护：禁右键、长按存图、选择复制、拖拽、打印快捷键 */
if(body.classList.contains('protect')){
  ['contextmenu','selectstart','dragstart','copy','cut'].forEach(function(ev){D.addEventListener(ev,function(e){if(e.target.closest&&e.target.closest('.qr'))return;e.preventDefault();});});
  D.addEventListener('keydown',function(e){if((e.ctrlKey||e.metaKey)&&/^[spcu]$/i.test(e.key))e.preventDefault();});
}
})();
