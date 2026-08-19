from rembg import remove
from PIL import Image
import numpy as np

im = Image.open("icon.png").convert("RGBA")
out = remove(im)

arr = np.array(out)
alpha = arr[:, :, 3]
ys, xs = np.where(alpha > 10)
top, bottom = ys.min(), ys.max()
left, right = xs.min(), xs.max()
pad = int(max(right - left, bottom - top) * 0.06)
left = max(0, left - pad)
top = max(0, top - pad)
right = min(arr.shape[1], right + pad)
bottom = min(arr.shape[0], bottom + pad)

cropped = out.crop((left, top, right, bottom))

w, h = cropped.size
side = max(w, h)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)

square.save("logo_square_transparent.png")
print("saved", square.size)
