import cv2
import numpy as np
from PIL import Image
import os

video_path = r"C:\Users\Owner\Downloads\D_minimalist_black_and_white.mp4"
output_dir = r"data\test_output"
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Reading {total_frames} frames from Video 2...")

# Let's sample every 2 frames: 0, 2, 4, ..., 238 -> 120 frames
sample_indices = list(range(0, total_frames, 2))

processed_frames = []

for idx in sample_indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, bgr = cap.read()
    if not ret:
        break
    
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h_f, w_f = gray.shape
    is_light = (gray > 160).astype(np.uint8)
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(is_light, connectivity=8)
    
    border_mask = np.zeros((h_f, w_f), dtype=bool)
    border_mask[0, :] = True
    border_mask[-1, :] = True
    border_mask[:, 0] = True
    border_mask[:, -1] = True
    
    border_labels = set(np.unique(labels[border_mask]))
    border_labels.discard(0)
    
    bg_mask = np.isin(labels, list(border_labels))
    
    for label_id in range(1, num_labels):
        if label_id in border_labels:
            continue
        area = stats[label_id, cv2.CC_STAT_AREA]
        cx, cy = centroids[label_id]
        
        # Bottom grass pockets
        if cy > 560 and area < 50000:
            bg_mask |= (labels == label_id)
        # Tail fold
        elif cx > 960 and cy > 460 and area < 20000:
            bg_mask |= (labels == label_id)
        # Front knee fold
        elif 320 <= cx <= 440 and 480 <= cy <= 620 and area < 10000:
            bg_mask |= (labels == label_id)
            
    # Soft alpha around edges
    dist = cv2.distanceTransform((~bg_mask).astype(np.uint8), cv2.DIST_L2, 3)
    alpha = np.clip(dist * 255.0 / 1.5, 0, 255).astype(np.uint8)
    alpha[bg_mask] = 0
    
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # Anti-halo black bleed on transparent pixels
    rgb[alpha == 0] = [0, 0, 0]
    
    rgba = np.dstack([rgb, alpha])
    processed_frames.append(rgba)

cap.release()
print(f"Processed {len(processed_frames)} frames.")

# Find global bounding box across all frames
min_x, min_y = 9999, 9999
max_x, max_y = 0, 0

for rgba in processed_frames:
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(xs) > 0:
        min_x = min(min_x, xs.min())
        max_x = max(max_x, xs.max())
        min_y = min(min_y, ys.min())
        max_y = max(max_y, ys.max())

print(f"Global bbox: x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]")

# We want aspect ratio 150:80 = 1.875, or fit nicely in 150x80
# Width = max_x - min_x + 1
# Height = max_y - min_y + 1
w_box = max_x - min_x + 1
h_box = max_y - min_y + 1
print(f"w_box: {w_box}, h_box: {h_box}, ratio: {w_box/h_box:.3f}")

# Target canvas 150x80
# Scale so that cow width fits comfortably (e.g. width=146, leaving 2px padding each side)
target_w = 150
target_h = 80

scale = 146.0 / w_box
new_w = int(round(w_box * scale))
new_h = int(round(h_box * scale))

print(f"Scaled size: {new_w}x{new_h}, target: {target_w}x{target_h}")

pil_frames = []
for rgba in processed_frames:
    # Crop to global bbox
    crop = rgba[min_y:max_y+1, min_x:max_x+1]
    # Resize with high quality Lanczos
    crop_img = Image.fromarray(crop, mode='RGBA')
    resized = crop_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Place on 150x80 canvas aligned at bottom
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = target_h - new_h # align to bottom so grass is at the pasture floor
    canvas.paste(resized, (offset_x, offset_y), resized)
    pil_frames.append(canvas)

# Save first frame as PNG
png_path = os.path.join(output_dir, "vaca_echada.png")
pil_frames[0].save(png_path)
print(f"Saved PNG to {png_path}")

# Save green test preview
green_bg = Image.new('RGB', (target_w, target_h), (34, 60, 36))
green_bg.paste(pil_frames[0], (0, 0), pil_frames[0])
green_preview_path = os.path.join(output_dir, "vaca_echada_green.png")
green_bg.save(green_preview_path)
print(f"Saved green preview to {green_preview_path}")

# Now build optimized GIF with transparency
# For GIF transparency:
# Quantize with a fixed transparent index
gif_frames = []
for img in pil_frames:
    # Convert RGBA to P with transparency
    # Split alpha
    r, g, b, a = img.split()
    # Mask out transparent
    mask = Image.eval(a, lambda p: 255 if p > 128 else 0)
    # Quantize RGB part
    rgb_im = Image.merge('RGB', (r, g, b))
    p_im = rgb_im.convert('P', palette=Image.Palette.ADAPTIVE, colors=63)
    # Put transparency
    # Set transparent color index 255
    p_arr = np.array(p_im)
    m_arr = np.array(mask)
    p_arr[m_arr == 0] = 255
    
    final_p = Image.fromarray(p_arr, mode='P')
    # Copy palette and set index 255 as transparent
    palette = p_im.getpalette()
    # Ensure palette has 256*3 entries
    while len(palette) < 256 * 3:
        palette.extend([0, 0, 0])
    palette[255*3:255*3+3] = [34, 60, 36] # fallback color
    final_p.putpalette(palette)
    final_p.info['transparency'] = 255
    final_p.info['duration'] = 80 # ms (12.5 fps)
    gif_frames.append(final_p)

gif_path = os.path.join(output_dir, "vaca_echada.gif")
gif_frames[0].save(
    gif_path,
    save_all=True,
    append_images=gif_frames[1:],
    loop=0,
    duration=80,
    disposal=2,
    transparency=255,
    optimize=False
)
print(f"Saved GIF to {gif_path}, size: {os.path.getsize(gif_path)} bytes")
