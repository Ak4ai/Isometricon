"""Vocabulário visual do atlas: papel, molduras e ícones vetoriais."""
from functools import lru_cache
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageOps


@lru_cache(maxsize=24)
def paper(width, height):
    image = Image.new('RGBA', (width,height), '#F2E8D1')
    d = ImageDraw.Draw(image)
    rng = random.Random(712)
    for _ in range(width*height//25):
        x,y = rng.randrange(width),rng.randrange(height)
        d.point((x,y),fill=rng.choice(('#E9DFC9','#F8EFDD','#EEE3CC')))
    # Linhas cartográficas quase imperceptíveis nas bordas do pergaminho.
    for i in range(6):
        d.arc((width-170+i*13, -150+i*13, width+180-i*6, 180-i*6), 65, 235, fill='#E5D8BA', width=1)
    return image


def panel(image, bounds):
    x,y,r,b = bounds
    shadow = Image.new('RGBA', image.size)
    d=ImageDraw.Draw(shadow)
    d.rounded_rectangle((x-3,y+8,r+3,b+16),16,fill=(4,18,14,130))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    w,h=int(r-x),int(b-y)
    mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),14,fill=255)
    image.paste(paper(w,h),(int(x),int(y)),mask)
    d=ImageDraw.Draw(image)
    d.rounded_rectangle(bounds,14,outline='#BAA373',width=2)
    d.rounded_rectangle((x+7,y+7,r-7,b-7),9,outline='#D4C5A4')
    # Cantos de metal com o mesmo motivo geométrico do símbolo.
    for cx,cy,dx,dy in ((x+15,y+15,1,1),(r-15,y+15,-1,1),(x+15,b-15,1,-1),(r-15,b-15,-1,-1)):
        d.line((cx,cy+18*dy,cx,cy,cx+18*dx,cy),fill='#A07E3F',width=2)
        d.polygon([(cx+5*dx,cy+9*dy),(cx+9*dx,cy+5*dy),(cx+13*dx,cy+9*dy),(cx+9*dx,cy+13*dy)],fill='#C4A25D')


def icon(draw, kind, x, y, size=22, color='#345246'):
    def pts(values):
        return [(x+a*size,y+b*size) for a,b in values]
    def line(values, width=2):
        draw.line(pts(values),fill=color,width=width,joint='curve')
    if kind in ('create','worlds','load','cube'):
        top=[(.5,.05),(.95,.28),(.5,.51),(.05,.28)]
        draw.polygon(pts(top),fill='#D8AE58',outline=color)
        draw.polygon(pts([(.05,.28),(.5,.51),(.5,.96),(.05,.72)]),fill='#769277',outline=color)
        draw.polygon(pts([(.5,.51),(.95,.28),(.95,.72),(.5,.96)]),fill='#355B4A',outline=color)
        if kind=='create':
            line([(.76,.55),(.76,.9)]);line([(.59,.73),(.93,.73)])
    elif kind=='settings':
        draw.ellipse((x+size*.25,y+size*.25,x+size*.75,y+size*.75),outline=color,width=2)
        for i in range(8):
            a=i*math.pi/4
            line([(.5+.32*math.cos(a),.5+.32*math.sin(a)),(.5+.47*math.cos(a),.5+.47*math.sin(a))])
        draw.ellipse((x+size*.43,y+size*.43,x+size*.57,y+size*.57),fill=color)
    elif kind=='credits':
        line([(.5,.22),(.1,.1),(.1,.8),(.5,.94),(.9,.8),(.9,.1),(.5,.22),(.5,.94)])
        line([(.21,.3),(.38,.36)]);line([(.62,.36),(.79,.3)])
    elif kind in ('exit','back'):
        line([(.65,.1),(.2,.1),(.2,.9),(.65,.9)])
        line([(.45,.5),(.95,.5),(.77,.3)]);line([(.95,.5),(.77,.7)])
    elif kind in ('delete','confirm_delete'):
        line([(.15,.2),(.85,.2)]);line([(.35,.2),(.35,.07),(.65,.07),(.65,.2)])
        line([(.25,.3),(.3,.93),(.7,.93),(.75,.3)]);line([(.43,.39),(.43,.77)]);line([(.58,.39),(.58,.77)])
    elif kind in ('game','play'):
        draw.polygon(pts([(.25,.1),(.85,.5),(.25,.9)]),fill=color)
    else:
        line([(.18,.5),(.42,.74),(.85,.18)])


@lru_cache(maxsize=96)
def seed_map(seed):
    """Prévia cartográfica determinística com o mesmo gerador de terreno."""
    from src.world import TerrainGenerator
    generator=TerrainGenerator(seed=seed)
    image=Image.new('RGB',(120,80),'#425C50');d=ImageDraw.Draw(image)
    for z in range(20):
        for x in range(30):
            h=generator.get_height((x-15)*2,(z-10)*2)
            color=('#426D78' if h<7 else '#B5AE7E' if h==7 else '#7D9561' if h<10 else '#496A4E')
            d.rectangle((x*4,z*4,x*4+3,z*4+3),fill=color)
    return image


@lru_cache(maxsize=64)
def _thumbnail(path, modified, seed):
    try:
        with Image.open(path) as image:
            return ImageOps.fit(image.convert('RGB'),(78,52),method=Image.Resampling.LANCZOS)
    except (OSError,ValueError):
        return seed_map(seed).resize((78,52),Image.Resampling.LANCZOS)


def world_thumbnail(library, world):
    path=library.directory/(world['id']+'.png')
    try:
        modified=path.stat().st_mtime_ns
    except OSError:
        modified=None
    return _thumbnail(str(path),modified,world['seed'])


@lru_cache(maxsize=1)
def atmosphere():
    """Vinheta suave: a paisagem permanece legível e a marca ganha contraste."""
    import numpy as np
    y,x = np.mgrid[0:876,0:1320]
    edge = ((x-660)/800)**2 + ((y-420)/650)**2
    alpha = np.clip(12 + 24*edge + 52*np.clip((700-x)/700,0,1) + 28*np.clip((y-550)/326,0,1),0,115)
    rgba=np.empty((876,1320,4),dtype=np.uint8)
    rgba[:,:,:3]=(9,25,20)
    rgba[:,:,3]=alpha.astype(np.uint8)
    return Image.fromarray(rgba)


@lru_cache(maxsize=8)
def menu_base(paused, bounds):
    """Sombra, papel e vinheta são superfícies estáticas compartilhadas."""
    image=Image.new('RGBA',(1320,876),(0,0,0,0))
    if not paused:
        image.alpha_composite(atmosphere())
    panel(image,bounds)
    return image



def warm_menu_surfaces():
    """Prepara os outros painéis enquanto a paisagem de apresentação carrega."""
    for paused,bounds in ((False,(400,24,920,828)),
                          (False,(36,24,1284,828)),
                          (True,(36,24,556,828))):
        menu_base(paused,bounds)
