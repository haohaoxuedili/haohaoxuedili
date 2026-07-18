from PIL import Image, ImageDraw

img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((32, 32, 480, 480), radius=96, fill=(11, 18, 32, 255))

for w in range(34, 0, -1):
    t = w / 34.0
    color = (int(0 * t + 0 * (1 - t)), int(198 * t + 114 * (1 - t)), int(255 * t + 255 * (1 - t)), 255)
    d.arc((96, 66, 448, 418), start=200, end=355, fill=color, width=w)
for off in range(0, 18):
    d.line((402, 160 + off, 446, 210 + off), fill=(0, 198, 255, 255), width=10)
    d.line((402, 160 + off, 366, 210 + off), fill=(0, 198, 255, 255), width=10)
for w in range(34, 0, -1):
    t = w / 34.0
    color = (int(127 * t + 225 * (1 - t)), int(0 * t + 0 * (1 - t)), int(255 * t + 255 * (1 - t)), 255)
    d.arc((96, 94, 448, 446), start=20, end=175, fill=color, width=w)
for off in range(0, 18):
    d.line((110, 356 + off, 66, 306 + off), fill=(225, 0, 255, 255), width=10)
    d.line((110, 356 + off, 146, 306 + off), fill=(225, 0, 255, 255), width=10)
for x1, y1, x2, y2 in [(180, 216, 196, 296), (214, 176, 230, 336), (248, 136, 264, 376), (282, 166, 298, 346)]:
    d.rounded_rectangle((x1, y1, x2, y2), radius=10, fill=(0, 198, 255, 255))

img.save('android/app.png')
print('android/app.png saved')
