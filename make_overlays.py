from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
B='/tmp/brand/'; O='/tmp/kit/overlays/'
W,H=1080,1920
NEG=(9,8,7); CARD=(12,11,9); ORO=(205,168,96); ORO2=(226,190,114); HUESO=(244,241,235); ROJO=(255,138,107)
def f(name,size,w):
    ft=ImageFont.truetype(B+'fonts/'+name,size); ft.set_variation_by_axes([w]); return ft
SG=lambda s:f('SG.ttf',s,700); PJ=lambda s,w=600:f('PJ.ttf',s,w)
def canvas(): return Image.new('RGBA',(W,H),(0,0,0,0))
def shadow(im,box,r=36,blur=30,a=150):
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle(box,r,fill=(0,0,0,a))
    return Image.alpha_composite(im,sh.filter(ImageFilter.GaussianBlur(blur)))
def tw(d,t,ft): return d.textbbox((0,0),t,font=ft)[2]
def logo(d,x,y,s=1.0,col=ORO):
    pts=[(2,12),(5,12),(7,6),(11,20),(15,2),(18,12),(22,12)]
    d.line([(x+px*3*s,y+py*3*s) for px,py in pts],fill=col,width=int(5*s),joint='curve')

# 1 gancho
im=canvas(); d=ImageDraw.Draw(im); ft=SG(92)
l1,l2='¿Pagas antes y','rezas que llegue?'
bw=max(tw(d,l1,ft),tw(d,l2,ft))+110; x0=(W-bw)//2; y0=250; box=(x0,y0,x0+bw,y0+290)
im=shadow(im,box); d=ImageDraw.Draw(im)
d.rounded_rectangle(box,34,fill=HUESO)
for i,t in enumerate([l1,l2]):
    d.text((W//2,y0+80+i*120),t,font=ft,fill=NEG,anchor='mm')
# subrayado "rezas"
xs=W//2-tw(d,l2,ft)//2; d.rectangle((xs,y0+243,xs+tw(d,'rezas',ft),y0+253),fill=ROJO)
sub='Así entregamos en DropAudio  ↓'; fs=PJ(40,700); sw=tw(d,sub,fs)+70
d.rounded_rectangle(((W-sw)//2,y0+320,(W+sw)//2,y0+400),40,fill=NEG+(225,),outline=ORO,width=3)
d.text((W//2,y0+360),sub,font=fs,fill=ORO2,anchor='mm')
im.save(O+'01_gancho.png')

# 2 chip dia de entregas
def chip(top,sub,y,name):
    im=canvas(); d=ImageDraw.Draw(im); a=SG(58); b=PJ(36,600)
    w=max(tw(d,top,a),tw(d,sub,b))+140; box=(70,y,70+w,y+170)
    im=shadow(im,box,30,24,120); d=ImageDraw.Draw(im)
    d.rounded_rectangle(box,30,fill=CARD+(235,),outline=ORO,width=3)
    d.rectangle((70,y+30,78,y+140),fill=ORO)
    d.text((115,y+30),top,font=a,fill=ORO2); d.text((115,y+105),sub,font=b,fill=HUESO)
    im.save(O+name)
chip('HOY: DÍA DE ENTREGAS','Caracas · Guarenas · Guatire en moto',1180,'02_entregas.png')

# 3/4 tarjetas de producto
def card(foto,nombre,precio,etiqueta,name):
    im=canvas(); w,h=520,760; x0,y0=W-w-60,740; box=(x0,y0,x0+w,y0+h)
    im=shadow(im,box,36,30,170); d=ImageDraw.Draw(im)
    d.rounded_rectangle(box,36,fill=CARD+(245,),outline=ORO,width=3)
    ph=ImageOps.fit(Image.open(B+foto).convert('RGB'),(w-40,520),centering=(0.5,0.55))
    m=Image.new('L',ph.size,0); ImageDraw.Draw(m).rounded_rectangle((0,0,*ph.size),26,fill=255)
    im.paste(ph,(x0+20,y0+20),m)
    d.text((x0+34,y0+568),nombre,font=SG(50),fill=HUESO)
    d.text((x0+34,y0+640),precio,font=SG(64),fill=ORO2)
    ft=PJ(28,700); tw_=tw(d,etiqueta,ft)+40
    d.rounded_rectangle((x0+40,y0+40,x0+40+tw_,y0+92),26,fill=NEG+(215,),outline=ORO,width=2)
    d.text((x0+60,y0+66),etiqueta,font=ft,fill=ORO2,anchor='lm')
    im.save(O+name)
card('castor.jpg','KZ Castor','desde $25','KZ original','03_castor.png')
card('y12-pro.jpg','Intercom Y12 Pro','$25','Bluetooth 5.4','04_y12.png')

# 5 prueba antes de pagar
im=canvas(); d=ImageDraw.Draw(im); t='El cliente prueba antes de pagar'; ft=SG(54)
w=tw(d,t,ft)+170; box=((W-w)//2,240,(W+w)//2,370)
im=shadow(im,box,65,24,130); d=ImageDraw.Draw(im)
d.rounded_rectangle(box,65,fill=CARD+(235,),outline=ORO,width=3)
cx=box[0]+70; d.ellipse((cx-30,275,cx+30,335),fill=ORO)
d.line([(cx-14,306),(cx-3,318),(cx+16,292)],fill=NEG,width=8,joint='curve')
d.text((cx+50,305),t,font=ft,fill=HUESO,anchor='lm')
im.save(O+'05_prueba.png')

# 6 CTA
im=canvas(); y0=1020; box=(90,y0,W-90,y0+500)
im=shadow(im,box,40,34,170); d=ImageDraw.Draw(im)
d.rounded_rectangle(box,40,fill=CARD+(240,),outline=ORO,width=3)
logo(d,W//2-33,y0+40,1.0)
d.text((W//2,y0+165),'Revisas. Escuchas.',font=SG(66),fill=HUESO,anchor='mm')
d.text((W//2,y0+245),'Luego pagas.',font=SG(66),fill=ORO2,anchor='mm')
bx=(170,y0+305,W-170,y0+400); d.rounded_rectangle(bx,26,fill=HUESO)
d.text((W//2,y0+352),'Comenta ASESORÍA',font=SG(52),fill=NEG,anchor='mm')
d.text((W//2,y0+450),'o escríbenos al 0422-1609357',font=PJ(38,600),fill=HUESO,anchor='mm')
im.save(O+'06_cta.png')

# hoja de prueba sobre fondo
sheet=Image.new('RGB',(W*3//2,H),(60,70,80)); 
for i,n in enumerate(['01_gancho','02_entregas','03_castor','04_y12','05_prueba','06_cta']):
    bg=Image.new('RGBA',(W,H),(70,85,95,255)); bg=Image.alpha_composite(bg,Image.open(O+n+'.png'))
    sheet.paste(bg.convert('RGB').resize((W//4,H//4)),((i%6)*W//4 if False else (i%3)*W//2,(i//3)*H//2))
sheet.resize((W*3//4,H//2)).save('/tmp/kit/sheet.jpg')

# ---- v3: fondos de producto a pantalla completa (se animan en CapCut con zoom + fundido) ----
def fill(path,size,blur=0,cent=(0.5,0.5)):
    im=ImageOps.fit(Image.open(path).convert('RGB'),size,centering=cent)
    return im.filter(ImageFilter.GaussianBlur(blur)) if blur else im
def grad(im,y0,y1,a=235):
    g=Image.new('L',(1,y1-y0)); g.putdata([int(a*(i/(y1-y0))**1.4) for i in range(y1-y0)])
    sh=Image.new('RGBA',(W,y1-y0),NEG+(0,)); sh.putalpha(g.resize((W,y1-y0)))
    im.alpha_composite(sh,(0,y0))
def etiqueta(d,x,y,nombre,precio,tag):
    ft=PJ(30,700); w_=tw(d,tag,ft)+44
    d.rounded_rectangle((x,y,x+w_,y+56),28,fill=NEG+(220,),outline=ORO,width=2)
    d.text((x+22,y+28),tag,font=ft,fill=ORO2,anchor='lm')
    d.text((x,y+80),nombre,font=SG(72),fill=HUESO)
    d.text((x,y+170),precio,font=SG(80),fill=ORO2)
def fondo(foto,nombre,precio,tag,name):
    im=fill(B+foto,(W,H),blur=40).convert('RGBA')
    im.alpha_composite(Image.new('RGBA',(W,H),NEG+(110,)))
    ph=fill(B+foto,(W,1300),cent=(0.5,0.6)).convert('RGBA'); im.alpha_composite(ph,(0,120))
    grad(im,900,H); d=ImageDraw.Draw(im)
    etiqueta(d,80,1300,nombre,precio,tag)
    im.convert('RGB').save(O+name,quality=92)
def fondo_doble(a,b,name):
    im=Image.new('RGBA',(W,H),NEG+(255,)); d=ImageDraw.Draw(im)
    for i,(foto,nombre,precio,tag) in enumerate([a,b]):
        y=i*(H//2); ph=fill(B+foto,(W,H//2),cent=(0.5,0.55)).convert('RGBA'); im.alpha_composite(ph,(0,y))
        grad(im,y+H//2-520,y+H//2,225); d=ImageDraw.Draw(im)
        etiqueta(d,80,y+H//2-330,nombre,precio,tag)
    d.rectangle((0,H//2-3,W,H//2+3),fill=ORO)
    im.convert('RGB').save(O+name,quality=92)
fondo('castor-pro.jpg','Castor · Castor Pro','$25 · $28','KZ original','bg_castor.jpg')
fondo_doble(('ae01.jpg','Módulo AE01','$35','Bluetooth para tus KZ'),
            ('y12-pro.jpg','Intercom Y12 Pro','$25','Casco a casco'),'bg_modulos_y12.jpg')

def chip_check(t,name,y=240):
    im=canvas(); d=ImageDraw.Draw(im); ft=SG(54)
    w=tw(d,t,ft)+170; box=((W-w)//2,y,(W+w)//2,y+130)
    im=shadow(im,box,65,24,130); d=ImageDraw.Draw(im)
    d.rounded_rectangle(box,65,fill=CARD+(235,),outline=ORO,width=3)
    cx=box[0]+70; cy=y+65; d.ellipse((cx-30,cy-30,cx+30,cy+30),fill=ORO)
    d.line([(cx-14,cy+1),(cx-3,cy+13),(cx+16,cy-13)],fill=NEG,width=8,joint='curve')
    d.text((cx+50,cy),t,font=ft,fill=HUESO,anchor='lm')
    im.save(O+name)
chip_check('Lo prueba antes de pagar','05_prueba.png')
chip_check('Le gustó: ahora sí paga','07_paga.png')
chip_check('Entrega en mano, en moto','08_entrega.png')
