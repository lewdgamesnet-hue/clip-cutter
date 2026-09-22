from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

out = Path(__file__).with_name('app.ico')
size = 256
im = Image.new('RGBA', (size,size), (0,0,0,0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((12,12,244,244), radius=48, fill=(22,24,30,255))
d.rounded_rectangle((38,54,218,202), radius=28, fill=(216,31,38,255))
d.polygon([(82,86),(82,170),(174,128)], fill='white')
try:
    font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 24)
except Exception:
    font = None
text='PCC'
bbox=d.textbbox((0,0),text,font=font)
d.text(((size-(bbox[2]-bbox[0]))/2, 211-(bbox[3]-bbox[1])), text, fill='white', font=font)
im.save(out, sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print(out)
