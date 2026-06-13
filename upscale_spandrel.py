#!/usr/bin/env python3
"""
Real-ESRGAN (and most other architectures) upscaler via spandrel + PyTorch CUDA.

Usage:
    python upscale_spandrel.py input.jpg [output.png] [--model PATH] [--tile 512]

Run with the project's venv:
    ~/odysseus/realesrgan-env/bin/python upscale_spandrel.py photo.jpg

spandrel auto-detects the architecture from the .pth/.safetensors weights, so the
same script works for RealESRGAN_x4plus, x2plus, anime models, SwinIR, etc.
"""
import argparse
import os
import sys
import torch
from PIL import Image
import numpy as np
from spandrel import ModelLoader

DEFAULT_MODEL = os.path.expanduser("~/odysseus/realesrgan-weights/RealESRGAN_x4plus.pth")


def to_tensor(img: Image.Image, device) -> torch.Tensor:
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)


def to_image(t: torch.Tensor) -> Image.Image:
    arr = t.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8))


def tiled_upscale(model, x: torch.Tensor, scale: int, tile: int, overlap: int = 16):
    """Process in tiles so large images don't OOM the GPU."""
    if tile <= 0:
        return model(x)
    _, _, h, w = x.shape
    out = torch.zeros((1, 3, h * scale, w * scale), device=x.device)
    for top in range(0, h, tile):
        for left in range(0, w, tile):
            b = min(top + tile + overlap, h)
            r = min(left + tile + overlap, w)
            t0 = max(top - overlap, 0)
            l0 = max(left - overlap, 0)
            patch = x[:, :, t0:b, l0:r]
            with torch.no_grad():
                sr = model(patch)
            # crop overlap back out, in output-space coords
            ct = (top - t0) * scale
            cl = (left - l0) * scale
            ph = (min(top + tile, h) - top) * scale
            pw = (min(left + tile, w) - left) * scale
            out[:, :, top * scale:top * scale + ph, left * scale:left * scale + pw] = \
                sr[:, :, ct:ct + ph, cl:cl + pw]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tile", type=int, default=512, help="tile size in px; 0 = no tiling")
    args = ap.parse_args()

    out_path = args.output or f"{os.path.splitext(args.input)[0]}_upscaled.png"
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = ModelLoader().load_from_file(args.model)
    model.to(device).eval()
    if device == "cuda":
        model.model.half() if False else None  # keep fp32 for quality; flip if you want speed
    scale = model.scale

    img = Image.open(args.input)
    x = to_tensor(img, device)
    sr = tiled_upscale(model, x, scale, args.tile)
    result = to_image(sr)
    result.save(out_path)
    print(f"{img.size} -> {result.size}  (x{scale})  [{device}]  -> {out_path}")


if __name__ == "__main__":
    main()
