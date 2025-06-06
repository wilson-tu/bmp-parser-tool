import tkinter as tk
from tkinter import filedialog, Label, Scale, Button, Checkbutton, IntVar
import struct
import numpy as np
from PIL import Image, ImageTk

original_pixels = None
img_tk = None
current_image = None

# Reads a BMP file as bytes
def read_bmp_file(filepath):
    with open(filepath, "rb") as f:
        return f.read()

# Parses BMP metadata and pixel data
def parse_bmp(bmp_bytes):
    if bmp_bytes[:2] != b'BM':
        raise ValueError("Invalid BMP file signature.")

    file_size = int.from_bytes(bmp_bytes[2:6], "little")
    pixel_offset = int.from_bytes(bmp_bytes[10:14], "little")
    dib_header_size = int.from_bytes(bmp_bytes[14:18], "little")
    width = int.from_bytes(bmp_bytes[18:22], "little")
    height = int.from_bytes(bmp_bytes[22:26], "little")
    bpp = int.from_bytes(bmp_bytes[28:30], "little")
    compression = int.from_bytes(bmp_bytes[30:34], "little")

    if compression != 0 or bpp not in [1, 4, 8, 24]:
        raise ValueError(f"Unsupported or compressed BMP format: {bpp} bpp")

    color_table = None
    if bpp in [1, 4, 8]:
        if len(bmp_bytes) >= 50:
            num_colors = int.from_bytes(bmp_bytes[46:50], "little")
        else:
            num_colors = 0
        if num_colors == 0:
            num_colors = 2 ** bpp
        color_table_size = num_colors * 4
        color_table_start = 14 + dib_header_size
        if len(bmp_bytes) < color_table_start + color_table_size:
            raise ValueError("Invalid BMP: Color table is missing.")
        color_table = bmp_bytes[color_table_start: color_table_start + color_table_size]

    row_size = ((bpp * width + 31) // 32) * 4
    pixels = np.zeros((height, width, 3), dtype=np.uint8)

    for row in range(height):
        row_start = pixel_offset + (height - 1 - row) * row_size
        row_data = bmp_bytes[row_start: row_start + row_size]
        if len(row_data) < row_size:
            row_data = row_data.ljust(row_size, b'\x00')

        if bpp == 24:
            row_pixels = []
            for i in range(width):
                offset = i * 3
                if offset + 3 <= len(row_data):
                    b, g, r = row_data[offset:offset+3]
                    row_pixels.append([r, g, b])
                else:
                    row_pixels.append([0, 0, 0])
            pixels[row] = np.array(row_pixels, dtype=np.uint8)
        else:
            pixel_indices = []
            if bpp == 8:
                pixel_indices = list(row_data[:width])
            elif bpp == 4:
                for byte in row_data[: (width + 1) // 2]:
                    pixel_indices.append(byte >> 4)
                    pixel_indices.append(byte & 0x0F)
                pixel_indices = pixel_indices[:width]
            elif bpp == 1:
                for byte in row_data[: (width + 7) // 8]:
                    for i in range(8):
                        pixel_indices.append((byte >> (7 - i)) & 1)
                pixel_indices = pixel_indices[:width]

            row_pixels = []
            for index in pixel_indices:
                if color_table and 0 <= index < len(color_table) // 4:
                    b, g, r, _ = struct.unpack("BBBB", color_table[index * 4:index * 4 + 4])
                    row_pixels.append([r, g, b])
                else:
                    row_pixels.append([255, 0, 255])
            while len(row_pixels) < width:
                row_pixels.append([0, 0, 0])
            pixels[row] = np.array(row_pixels, dtype=np.uint8)

    return file_size, width, height, bpp, pixels

# Scales an image manually
def scale_image_manual(image, scale_factor):
    height, width, _ = image.shape
    new_width = max(1, int(width * scale_factor))
    new_height = max(1, int(height * scale_factor))
    new_image = np.zeros((new_height, new_width, 3), dtype=np.uint8)
    orig_x = (np.arange(new_width) / scale_factor).astype(int)
    orig_y = (np.arange(new_height) / scale_factor).astype(int)
    orig_x = np.clip(orig_x, 0, width - 1)
    orig_y = np.clip(orig_y, 0, height - 1)
    new_image[:, :] = image[orig_y[:, None], orig_x]
    return new_image

# Opens a BMP file and displays it
def open_file():
    global original_pixels, img_tk, current_image
    filepath = filedialog.askopenfilename(filetypes=[("BMP files", "*.bmp")])
    if filepath:
        try:
            file_size, width, height, bpp, pixels = parse_bmp(read_bmp_file(filepath))
            metadata = f"File Size: {file_size} bytes\nWidth: {width} px\nHeight: {height} px\nBits Per Pixel: {bpp}"
            metadata_label.config(text=metadata)

            original_pixels = pixels
            current_image = np.copy(original_pixels)

            # Reset to default
            brightness_slider.set(100)
            scale_slider.set(100)
            r_enabled.set(1)
            g_enabled.set(1)
            b_enabled.set(1)

            img_pil = Image.fromarray(current_image)
            img_tk = ImageTk.PhotoImage(img_pil)
            image_label.config(image=img_tk)
            image_label.image = img_tk
        except ValueError as e:
            metadata_label.config(text=f"Error: {str(e)}")
            original_pixels = None
            current_image = None

# Scales the image and applies toggled channels
def apply_scaling(value):
    global original_pixels, img_tk, current_image
    if original_pixels is None:
        return
    scale_factor = int(value) / 100
    current_image = scale_image_manual(original_pixels, scale_factor)
    brightness_factor = brightness_slider.get() / 100
    modified_image = np.clip(current_image * brightness_factor, 0, 255).astype(np.uint8)
    if r_enabled.get() == 0:
        modified_image[:, :, 0] = 0
    if g_enabled.get() == 0:
        modified_image[:, :, 1] = 0
    if b_enabled.get() == 0:
        modified_image[:, :, 2] = 0
    img_pil = Image.fromarray(modified_image)
    img_tk = ImageTk.PhotoImage(img_pil)
    image_label.config(image=img_tk)
    image_label.image = img_tk

# Adjusts brightness and applies toggled channels
def adjust_brightness(value):
    global original_pixels, img_tk, current_image
    if original_pixels is None:
        return
    brightness_factor = int(value) / 100
    base_image = current_image if current_image is not None else original_pixels
    modified_image = np.clip(base_image * brightness_factor, 0, 255).astype(np.uint8)
    if r_enabled.get() == 0:
        modified_image[:, :, 0] = 0
    if g_enabled.get() == 0:
        modified_image[:, :, 1] = 0
    if b_enabled.get() == 0:
        modified_image[:, :, 2] = 0
    img_pil = Image.fromarray(modified_image)
    img_tk = ImageTk.PhotoImage(img_pil)
    image_label.config(image=img_tk)
    image_label.image = img_tk

# Toggles RGB channels
def toggle_channels():
    global original_pixels, img_tk, current_image
    if original_pixels is None:
        return
    brightness_factor = brightness_slider.get() / 100
    modified_image = np.clip(current_image * brightness_factor, 0, 255).astype(np.uint8)
    if r_enabled.get() == 0:
        modified_image[:, :, 0] = 0
    if g_enabled.get() == 0:
        modified_image[:, :, 1] = 0
    if b_enabled.get() == 0:
        modified_image[:, :, 2] = 0
    img_pil = Image.fromarray(modified_image)
    img_tk = ImageTk.PhotoImage(img_pil)
    image_label.config(image=img_tk)
    image_label.image = img_tk

# Initialize the GUI and add interactive widgets
root = tk.Tk()
root.title("BMP Viewer")
root.geometry("900x700")

open_button = tk.Button(root, text="Open BMP", command=open_file, bg="lightgreen")
open_button.pack(pady=10)

metadata_label = Label(root, text="Metadata will appear here", justify="left")
metadata_label.pack(pady=10)

image_label = Label(root)
image_label.pack(pady=10)

brightness_label = Label(root, text="Adjust Brightness", bg="lightgreen", fg="black")
brightness_label.pack(pady=(10, 0))
brightness_slider = Scale(root, from_=0, to=100, orient="horizontal", command=adjust_brightness)
brightness_slider.set(100)
brightness_slider.pack()

scale_label = Label(root, text="Scale Image", bg="lightgreen", fg="black")
scale_label.pack(pady=(10, 0))
scale_slider = Scale(root, from_=10, to=100, orient="horizontal", command=apply_scaling)
scale_slider.set(100)
scale_slider.pack()

r_enabled, g_enabled, b_enabled = IntVar(value=1), IntVar(value=1), IntVar(value=1)
Checkbutton(root, text="Red", variable=r_enabled, command=toggle_channels).pack()
Checkbutton(root, text="Green", variable=g_enabled, command=toggle_channels).pack()
Checkbutton(root, text="Blue", variable=b_enabled, command=toggle_channels).pack()

root.mainloop()