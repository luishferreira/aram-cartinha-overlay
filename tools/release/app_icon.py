"""Draw the original card mark used by the executable and Tk windows."""
from pathlib import Path


def build():
    from PIL import Image,ImageDraw
    folder=Path(__file__).resolve().parents[2]/'assets'
    folder.mkdir(exist_ok=True)
    image=Image.new('RGBA',(1024,1024),(0,0,0,0))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((24,24,1000,1000),radius=220,fill='#101b29')
    draw.rounded_rectangle((184,160,702,816),radius=64,fill='#263c50',outline='#91b0c1',width=24)
    draw.rounded_rectangle((304,220,840,896),radius=64,fill='#183b43',outline='#7edbc4',width=32)
    draw.polygon([(572,344),(622,480),(758,530),(622,580),(572,716),(522,580),(386,530),(522,480)],fill='#f3cf7a')
    draw.rounded_rectangle((454,784,690,808),radius=12,fill='#7edbc4')
    image=image.resize((256,256),Image.Resampling.LANCZOS)
    image.save(folder/'app.png')
    image.save(folder/'app.ico',sizes=[(s,s) for s in (16,20,24,32,40,48,64,128,256)])


if __name__=='__main__':build()
