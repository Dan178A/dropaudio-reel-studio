"""Cama musical DropAudio para reel hablado: suave bajo la voz, golpes en los cambios. 128 BPM, numpy, sin derechos."""
import numpy as np, sys, json, wave
SR=44100; BPM=128; beat=60/BPM
def music(total, cues, drop, cta, out):
    n=int(total*SR); t=np.arange(n)/SR; mix=np.zeros(n)
    def add(sig,at,g=1.0):
        i=int(at*SR); j=min(n,i+len(sig)); 
        if i<n: mix[i:j]+=g*sig[:j-i]
    env=lambda L,a,d: np.minimum(1,np.arange(L)/(a*SR+1))*np.exp(-np.arange(L)/(d*SR))
    # pad (acordes Am-F-C-G) con sidechain
    prog=[[220,261.6,329.6],[174.6,220,261.6],[261.6,329.6,392],[196,246.9,293.7]]
    bar=4*beat; pad=np.zeros(n)
    for k in range(int(total/bar)+1):
        L=int(bar*SR); tt=np.arange(L)/SR
        ch=sum(np.sin(2*np.pi*f*tt+np.sin(2*np.pi*0.3*tt))+0.5*np.sin(2*np.pi*f*1.005*tt) for f in prog[k%4])
        i=k*L; j=min(n,i+L); pad[i:j]+=ch[:j-i]
    side=1-0.6*np.exp(-((t%beat)/0.12)); pad*=side
    lvl=np.where(t<drop,0.05,0.075); pad*=lvl
    mix+=pad
    # kick: suave antes del drop, completo después
    k=np.sin(2*np.pi*(45+90*np.exp(-np.arange(int(.35*SR))/(.03*SR)))*np.arange(int(.35*SR))/SR)*env(int(.35*SR),.002,.12)
    for b in np.arange(0,total,beat):
        add(k,b,0.10 if b<drop else 0.28)
    # hats después del drop
    rng=np.random.default_rng(1); h=rng.standard_normal(int(.05*SR))*env(int(.05*SR),.001,.012)
    for b in np.arange(drop+beat/2,total,beat): add(h,b,0.05)
    # golpes (impact) y pops
    imp=(np.sin(2*np.pi*55*np.arange(int(1.2*SR))/SR)+0.4*rng.standard_normal(int(1.2*SR))*np.exp(-np.arange(int(1.2*SR))/(.05*SR)))*env(int(1.2*SR),.002,.35)
    for c in [0,drop,cta]: add(imp,c,0.45)
    pop=np.sin(2*np.pi*(900+600*np.exp(-np.arange(int(.12*SR))/(.01*SR)))*np.arange(int(.12*SR))/SR)*env(int(.12*SR),.001,.03)
    for c in cues: add(pop,c,0.18)
    # riser antes del drop
    L=int(1.5*SR); r=rng.standard_normal(L)*np.linspace(0,1,L)**2
    r=np.convolve(r,np.ones(8)/8,'same'); add(r,drop-1.5,0.12)
    mix*=np.minimum(1,(total-t)/0.8)  # fade final
    mix=mix/np.max(np.abs(mix))*0.5   # ~-6 dBFS pico, cama baja
    st=np.stack([mix,mix],1)
    with wave.open(out,'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st*32767).astype(np.int16).tobytes())
if __name__=='__main__':
    import sys  # uso: python gen_music.py total drop cta salida.wav [pops...]
    a=sys.argv[1:]; music(float(a[0]),[float(x) for x in a[4:]],float(a[1]),float(a[2]),a[3])
