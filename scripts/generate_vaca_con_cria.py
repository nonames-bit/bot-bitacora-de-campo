import cv2
import numpy as np
from PIL import Image
import os

video_path = r"C:\Users\Owner\Downloads\D_minimalist_black_and_white (1).mp4"
output_dir = r"data\test_output"
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Processing Video 1: {total_frames} frames...")

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
    
    # Identify background pockets:
    for i in range(1, num_labels):
        if i in border_labels:
            continue
        area = stats[i, cv2.CC_STAT_AREA]
        cx, cy = centroids[i]
        
        is_pocket = False
        if cy > 600:
            is_pocket = True
        elif 140 <= cx <= 360 and 450 <= cy <= 620:
            is_pocket = True
        elif 250 <= cx <= 460 and 480 <= cy <= 630:
            is_pocket = True
        elif 450 <= cx <= 710 and 440 <= cy <= 630:
            is_pocket = True
        elif 600 <= cx <= 740 and 380 <= cy <= 510 and area < 10000:
            is_pocket = True
        elif 700 <= cx <= 890 and 460 <= cy <= 640 and area < 15000:
            is_pocket = True
        elif 880 <= cx <= 1060 and 490 <= cy <= 640 and area < 15000:
            is_pocket = True
            
        if is_pocket:
            bg_mask |= (labels == i)

    # Soft alpha
    dist = cv2.distanceTransform((~bg_mask).astype(np.uint8), cv2.DIST_L2, 3)
    alpha = np.clip(dist * 255.0 / 1.5, 0, 255).astype(np.uint8)
    alpha[bg_mask] = 0
    
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb[alpha == 0] = [0, 0, 0]
    
    rgba = np.dstack([rgb, alpha])
    processed_frames.append(rgba)

cap.release()
print(f"Processed {len(processed_frames)} frames.")

# Global bbox
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

w_box = max_x - min_x + 1
h_box = max_y - min_y + 1

target_w = 150
target_h = 80

scale = 146.0 / w_box
new_w = int(round(w_box * scale))
new_h = int(round(h_box * scale))

pil_frames = []
for frame_i, rgba in enumerate(processed_frames):
    crop = rgba[min_y:max_y+1, min_x:max_x+1]
    crop_img = Image.fromarray(crop, mode='RGBA')
    resized = crop_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = target_h - new_h
    canvas.paste(resized, (offset_x, offset_y), resized)
    
    arr = np.array(canvas)
    orig_frame = sample_indices[frame_i]
    
    # 1. Horn removal according to precise state
    if 112 <= orig_frame <= 148:
        # Turned head state: horns are in x: 55..74, y: 10..22 against black shoulder
        for y in range(10, 22):
            for x in range(55, 74):
                if arr[y, x, 3] > 50 and np.mean(arr[y, x, :3]) > 70:
                    arr[y, x] = [0, 0, 0, 255]
    elif orig_frame <= 108 or orig_frame >= 152:
        # Grazing state:
        # Left horn: completely erase pixels at x <= 14, y in 35..52 to transparent
        for y in range(35, 52):
            for x in range(4, 15):
                arr[y, x] = [0, 0, 0, 0]
        # Right horn: merge light pixels into black neck
        for y in range(33, 43):
            for x in range(15, 23):
                if arr[y, x, 3] > 50 and np.mean(arr[y, x, :3]) > 75:
                    arr[y, x] = [0, 0, 0, 255]
    
    # 2. Clean any isolated floating specks in upper-left (area < 15)
    alpha_bin = (arr[:, :, 3] > 10).astype(np.uint8)
    n_l, l_map, s_arr, _ = cv2.connectedComponentsWithStats(alpha_bin, connectivity=8)
    for l_idx in range(1, n_l):
        comp_area = s_arr[l_idx, cv2.CC_STAT_AREA]
        comp_x = s_arr[l_idx, cv2.CC_STAT_LEFT]
        comp_y = s_arr[l_idx, cv2.CC_STAT_TOP]
        # If small island (< 15 px) in the air/sky (y < 55, x < 40)
        if comp_area < 15 and comp_y < 55 and comp_x < 40:
            arr[l_map == l_idx] = [0, 0, 0, 0]

    clean_canvas = Image.fromarray(arr, mode='RGBA')
    pil_frames.append(clean_canvas)

# Save first frame preview
png_path = os.path.join(output_dir, "vaca_con_cria.png")
pil_frames[0].save(png_path)
print(f"Saved PNG to {png_path}")

# Build transparent GIF
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

gif_path = os.path.join(output_dir, "vaca_con_cria.gif")
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
