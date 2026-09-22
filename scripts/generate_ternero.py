import cv2
import numpy as np
from PIL import Image
import os
import shutil

video_path = r"C:\Users\Owner\Downloads\gemini_generated_video_b29b450f.mp4"
static_dir = r"src\pwa\static"
out_dir = r"data\test_output"
os.makedirs(static_dir, exist_ok=True)
os.makedirs(out_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Reading {total_frames} frames sequentially...")

processed_frames = []
frame_idx = 0

while True:
    ret, bgr = cap.read()
    if not ret:
        break
    
    # Sample every 2nd frame (120 frames total -> 9.6s loop at 80ms)
    if frame_idx % 2 != 0:
        frame_idx += 1
        continue
    
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h_f, w_f = gray.shape
    
    # Force pure white background outside calf bounds
    gray[:170, :] = 255
    gray[670:, :] = 255
    gray[:, :240] = 255
    gray[:, 1010:] = 255
    
    is_light = (gray > 165).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(is_light, connectivity=8)
    
    border_mask = np.zeros((h_f, w_f), dtype=bool)
    border_mask[0, :] = True
    border_mask[-1, :] = True
    border_mask[:, 0] = True
    border_mask[:, -1] = True
    
    border_labels = set(np.unique(labels[border_mask]))
    border_labels.discard(0)
    bg_mask = np.isin(labels, list(border_labels))
    
    # Remove internal trapped background pockets:
    for i in range(1, num_labels):
        if i in border_labels:
            continue
        cx, cy = centroids[i]
        area = stats[i, cv2.CC_STAT_AREA]
        
        is_bg = False
        # Under belly / between legs
        if 360 <= cx <= 760 and 410 < cy < 630:
            is_bg = True
        # Under raised tail (when kicking)
        elif cx < 360 and 200 < cy < 420 and area < 8000:
            is_bg = True
        # Distant grass specks far to sides at bottom
        elif (cx < 260 or cx > 980) and cy > 570:
            is_bg = True
            
        if is_bg:
            bg_mask |= (labels == i)
            
    # Force background on outer margin
    bg_mask[:170, :] = True
    bg_mask[670:, :] = True
    bg_mask[:, :240] = True
    bg_mask[:, 1010:] = True
    
    # Soft alpha around edges
    dist = cv2.distanceTransform((~bg_mask).astype(np.uint8), cv2.DIST_L2, 3)
    alpha = np.clip(dist * 255.0 / 1.5, 0, 255).astype(np.uint8)
    alpha[bg_mask] = 0
    alpha[:170, :] = 0
    alpha[670:, :] = 0
    alpha[:, :240] = 0
    alpha[:, 1010:] = 0
    
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # Anti-halo black bleed on transparent pixels
    rgb[alpha == 0] = [0, 0, 0]
    
    rgba = np.dstack([rgb, alpha])
    processed_frames.append(rgba)
    frame_idx += 1

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
w_box = max_x - min_x + 1
h_box = max_y - min_y + 1
print(f"w_box: {w_box}, h_box: {h_box}, ratio: {w_box/h_box:.3f}")

target_w = 150
target_h = 80

scale = min(142.0 / w_box, 75.0 / h_box)
new_w = int(round(w_box * scale))
new_h = int(round(h_box * scale))
print(f"Scaled size: {new_w}x{new_h}, target canvas: {target_w}x{target_h}")

pil_frames = []
for rgba in processed_frames:
    crop = rgba[min_y:max_y+1, min_x:max_x+1]
    crop_img = Image.fromarray(crop, mode='RGBA')
    resized = crop_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = target_h - new_h # align to bottom
    canvas.paste(resized, (offset_x, offset_y), resized)
    pil_frames.append(canvas)

# Save preview PNG
png_dest = os.path.join(static_dir, "ternero.png")
pil_frames[0].save(png_dest)
print(f"Saved PNG to {png_dest}, size: {os.path.getsize(png_dest)} bytes")

# Build transparent GIF with adaptive palette
gif_frames = []
for img in pil_frames:
    r, g, b, a = img.split()
    mask = Image.eval(a, lambda p: 255 if p > 128 else 0)
    rgb_im = Image.merge('RGB', (r, g, b))
    p_im = rgb_im.convert('P', palette=Image.Palette.ADAPTIVE, colors=63)
    
    p_arr = np.array(p_im)
    m_arr = np.array(mask)
    p_arr[m_arr == 0] = 255
    
    final_p = Image.fromarray(p_arr, mode='P')
    palette = p_im.getpalette()
    while len(palette) < 256 * 3:
        palette.extend([0, 0, 0])
    palette[255*3:255*3+3] = [34, 60, 36]
    final_p.putpalette(palette)
    final_p.info['transparency'] = 255
    final_p.info['duration'] = 80
    gif_frames.append(final_p)

gif_dest = os.path.join(static_dir, "ternero.gif")
gif_frames[0].save(
    gif_dest,
    save_all=True,
    append_images=gif_frames[1:],
    loop=0,
    duration=80,
    disposal=2,
    transparency=255,
    optimize=False
)
print(f"Saved GIF to {gif_dest}, size: {os.path.getsize(gif_dest)} bytes")

# Copy original MP4 video to static/ternero.mp4
mp4_dest = os.path.join(static_dir, "ternero.mp4")
shutil.copyfile(video_path, mp4_dest)
print(f"Copied MP4 to {mp4_dest}, size: {os.path.getsize(mp4_dest)} bytes")

# Green background preview for visual verification
green_bg = Image.new('RGB', (target_w, target_h), (34, 60, 36))
green_bg.paste(pil_frames[0], (0, 0), pil_frames[0])
green_dest = os.path.join(out_dir, "ternero_composite_preview.png")
green_bg.save(green_dest)
print(f"Saved green composite preview to {green_dest}")
