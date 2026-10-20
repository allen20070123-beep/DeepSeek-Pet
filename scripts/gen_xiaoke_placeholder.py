import math, os, subprocess, shutil, sys
from PIL import Image
W,H,FEET,FH,FPS=640,360,330,258,24
SRC={k:Image.open(k+'.png') for k in ('front','side','back')}
FLOWER=Image.open('flower.png'); HEART=Image.open('heart.png')
cache={}
def sprite(key,sx,sy,mirror=False):
    src=SRC[key]; k=(key,round(sx,3),round(sy,3),mirror)
    if k in cache: return cache[k]
    s=FH/src.height
    w=max(1,int(src.width*s*sx)); h=max(1,int(src.height*s*sy))
    im=src.resize((w,h),Image.LANCZOS)
    if mirror: im=im.transpose(Image.FLIP_LEFT_RIGHT)
    if len(cache)>400: cache.clear()
    cache[k]=im; return im
def place(cv,key,cx=320,feet=FEET,sx=1,sy=1,rot=0,mirror=False,pivot='feet'):
    im=sprite(key,sx,sy,mirror)
    w,h=im.size
    if rot:
        # 整层绕支点旋转：feet=脚底中心，top=头顶中心
        layer=Image.new('RGBA',cv.size,(0,0,0,0)); layer.alpha_composite(im,(int(cx-w/2),int(feet-h)))
        py=feet if pivot=='feet' else feet-h
        cv.alpha_composite(layer.rotate(rot,resample=Image.BICUBIC,center=(cx,py)))
        return
    cv.alpha_composite(im,(int(cx-w/2),int(feet-h)))
def deco(cv,img,x,y,size,rot=0,alpha=1.0):
    if alpha<=0 or size<2: return
    im=img.resize((int(size),int(size)),Image.LANCZOS)
    if rot: im=im.rotate(rot,resample=Image.BICUBIC)
    if alpha<1:
        a=im.split()[3].point(lambda v:int(v*alpha)); im.putalpha(a)
    cv.alpha_composite(im,(int(x-size/2),int(y-size/2)))
ease=lambda u:0.5-0.5*math.cos(math.pi*max(0,min(1,u)))
def breathe(t,amp=1.0):
    b=math.sin(2*math.pi*t/3.2)
    return 1-0.003*b*amp, 1+0.007*b*amp
def squeeze_seq(cv,u,frm,to,feet=FEET,mto=False,mfrm=False):
    # u 0..1: frm squeezes to 0 then to expands
    if u<0.5: place(cv,frm,sx=max(0.02,math.cos(math.pi*u)),feet=feet,mirror=mfrm)
    else: place(cv,to,sx=max(0.02,-math.cos(math.pi*u)),feet=feet,mirror=mto)
def spin(cv,u,feet=FEET):
    seq=[('front',False),('side',False),('back',False),('side',True),('front',False)]
    seg=min(3,int(u*4)); v=u*4-seg
    squeeze_seq(cv,v,seq[seg][0],seq[seg+1][0],feet,mto=seq[seg+1][1],mfrm=seq[seg][1])
def hop_y(t,t0,dur=0.7,h=28):
    u=(t-t0)/dur
    return -h*4*u*(1-u) if 0<=u<=1 else 0
def squash(t,t0,dur=0.7):
    for c,s in ((t0-0.15,0.15),(t0+dur,0.18)):
        u=(t-c)/s
        if 0<=u<=1: return 1-0.05*math.sin(math.pi*u)
    return 1

def A_idle(cv,t,T): sx,sy=breathe(t); place(cv,'front',sx=sx,sy=sy)
def A_turn(cv,t,T):
    if t<1: A_idle(cv,t,T)
    elif t<1.4: squeeze_seq(cv,(t-1)/0.4,'front','side')
    elif t<4.6: place(cv,'side',sy=1+0.005*math.sin(t*2.5),rot=1.2*math.sin((t-1.4)*1.6))
    elif t<5: squeeze_seq(cv,(t-4.6)/0.4,'side','front')
    else: A_idle(cv,t,T)
def make_walk(period,amp,tilt):
    def f(cv,t,T):
        if t<1.6 or t>=8.4: A_idle(cv,t,T)
        elif t<2: squeeze_seq(cv,(t-1.6)/0.4,'front','side')
        elif t<8:
            p=(t-2)/period
            place(cv,'side',feet=FEET-abs(math.sin(math.pi*p))*amp,rot=tilt*math.sin(2*math.pi*p))
        else: squeeze_seq(cv,(t-8)/0.4,'side','front')
    return f
def A_drag(cv,t,T):
    lift=24*ease(t/0.4)*(1-ease((t-(T-0.6))/0.6))
    rot=5*math.sin(2*math.pi*t/1.6)*min(1,t/0.6)*(1-ease((t-(T-0.8))/0.8))
    place(cv,'front',feet=FEET-lift,rot=rot,pivot='top')
def A_hop_hearts(cv,t,T):
    y=hop_y(t,0.6); s=squash(t,0.6)
    place(cv,'front',feet=FEET+y,sy=s,sx=2-s)
    for i,(dx,t0) in enumerate(((-55,0.9),(50,1.2),(0,1.5))):
        u=(t-t0)/1.8
        if 0<=u<=1: deco(cv,HEART,320+dx+6*math.sin(u*6),60-40*u+ (0 if i!=2 else -10),26+10*math.sin(math.pi*u),alpha=math.sin(math.pi*u))
def A_spin(cv,t,T):
    if t<0.5 or t>=3.5: A_idle(cv,t,T)
    else: spin(cv,ease((t-0.5)/3.0))
def A_shy(cv,t,T):
    shake=4*math.sin(2*math.pi*t*3)*max(0,1-t/2.5)
    sx,sy=breathe(t); place(cv,'front',cx=320+shake,sx=sx,sy=sy*(1-0.01*max(0,1-t/2.5)))
    u=(t-0.3)/2.4
    if 0<=u<=1: deco(cv,HEART,385,70-20*u,30,rot=-15,alpha=math.sin(math.pi*u))
def A_bloom(cv,t,T):
    A_idle(cv,t,T)
    for i in range(6):
        ang=i*60+t*25; u=(t-0.3-i*0.12)/3.8
        if 0<=u<=1:
            r=40+50*ease(min(1,u*2)); a=math.radians(ang)
            deco(cv,FLOWER,320+r*1.6*math.cos(a),80+r*0.6*math.sin(a),12+22*ease(min(1,u*2.5)),rot=ang*2,alpha=min(1,(1-u)*3))
def make_balance(n,droop=False):
    def f(cv,t,T):
        sx,sy=breathe(t)
        if droop: sy*=1-0.015*ease(t/1.5); 
        place(cv,'front',sx=sx,sy=sy,rot=(1.5*ease(t/1.5) if droop else 0))
        for i in range(n):
            u=((t/T)+i/n)%1
            x=320+(-120+240*((i*37)%n)/max(1,n-1) if n>1 else 0)+10*math.sin(u*6+i)
            deco(cv,FLOWER,x,330-260*u,18+(i%3)*4,rot=u*360,alpha=math.sin(math.pi*u)*0.9)
    return f
def A_sway(cv,t,T):
    sx,sy=breathe(t); place(cv,'front',sx=sx,sy=sy,rot=2.5*math.sin(2*math.pi*t/5)*min(1,t)*min(1,(T-t)))
def A_slowspin(cv,t,T):
    if t<1 or t>=5: A_idle(cv,t,T)
    else: spin(cv,ease((t-1)/4))
def A_petals(cv,t,T):
    A_idle(cv,t,T)
    for i in range(9):
        u=((t/T)*1.5+i/9)%1; fade=min(1,t/0.8,(T-t)/0.8)
        deco(cv,FLOWER,180+i*35+18*math.sin(u*7+i),20+300*u,14+(i%3)*3,rot=u*500+i*40,alpha=math.sin(math.pi*u)*0.85*fade)
def A_orbit(cv,t,T):
    fade=min(1,t/1,(T-t)/1)
    back=[];front=[]
    for i in range(5):
        a=2*math.pi*(i/5)+t*1.3; x=320+120*math.cos(a); y=200+30*math.sin(a); s=22+6*math.sin(a)
        (front if math.sin(a)>0 else back).append((x,y,s,math.degrees(a)*2))
    for x,y,s,r in back: deco(cv,FLOWER,x,y,s*0.85,rot=r,alpha=0.75*fade)
    A_idle(cv,t,T)
    for x,y,s,r in front: deco(cv,FLOWER,x,y,s,rot=r,alpha=fade)
def A_doublehop(cv,t,T):
    y=hop_y(t,0.8)+hop_y(t,2.0,0.7,22); s=min(squash(t,0.8),squash(t,2.0))
    if t<0.6 or t>3: A_idle(cv,t,T)
    else: place(cv,'front',feet=FEET+y,sy=s,sx=2-s)

ANIMS={
 '小克-待机呼吸':(A_idle,10),'小克-回头张望':(A_turn,6),
 '小克-轻步走':(make_walk(0.55,5,1.5),10),'小克-小跑':(make_walk(0.36,8,2.5),10),
 '小克-被拎起':(A_drag,8),
 '小克-开心跳跃':(A_hop_hearts,4),'小克-转圈展示':(A_spin,4),'小克-害羞摇晃':(A_shy,4),'小克-向日葵绽放':(A_bloom,5),
 '小克-余量充足':(make_balance(10),6),'小克-余量宽裕':(make_balance(8),6),'小克-余量如常':(make_balance(6),6),
 '小克-余量偏少':(make_balance(4),6),'小克-余量告急':(make_balance(2),6),'小克-余量用尽':(make_balance(0,True),6),
 '小克-轻轻摇摆':(A_sway,10),'小克-优雅转身':(A_slowspin,6),'小克-花瓣飘落':(A_petals,10),
 '小克-向日葵环绕':(A_orbit,10),'小克-连跳':(A_doublehop,4),
}
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
only=sys.argv[2:] or list(ANIMS)
for name in only:
    fn,T=ANIMS[name]; d='frames_tmp'; shutil.rmtree(d,ignore_errors=True); os.makedirs(d)
    n=int(T*FPS)
    for i in range(n):
        cv=Image.new('RGBA',(W,H),(0,0,0,0)); fn(cv,i/FPS,T); cv.save(f'{d}/{i:04d}.png')
    subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(FPS),'-i',f'{d}/%04d.png','-c:v','libvpx-vp9','-pix_fmt','yuva420p','-crf','30','-b:v','0','-row-mt','1','-an',f'{out}/{name}.webm'],check=True)
    print(name,n,os.path.getsize(f'{out}/{name}.webm')//1024,'KB',flush=True)
