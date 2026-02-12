"""ComfyUI image generation engine."""

import random
import time
import requests as req


def generate_image(
    prompt: str,
    server: str,
    checkpoint: str,
    steps: int = 20,
    seed: int | None = None,
    width: int = 512,
    height: int = 512,
    negative_prompt: str = "photograph, photo, realistic, 3d render, animal, cat, dog, bear, lion, eagle, wolf, fox, owl, bird, furry, anthropomorphic, cartoon animal, animal character, blurry, deformed, ugly, watermark, signature, black and white, grayscale, monochrome, sepia, desaturated",
) -> bytes:
    """Send a prompt to ComfyUI and return image bytes."""
    if seed is None:
        seed = random.randint(1, 2**31)

    workflow = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["4", 1]}},
        "10": {"class_type": "FluxGuidance", "inputs": {"guidance": 3.5, "conditioning": ["6", 0]}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1, "model": ["4", 0],
            "positive": ["10", 0], "negative": ["7", 0], "latent_image": ["5", 0],
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "api_panel", "images": ["8", 0]}},
    }

    resp = req.post(f"{server}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    for _ in range(300):  # max ~5 min per panel
        hist = req.get(f"{server}/history/{prompt_id}", timeout=10).json()
        if prompt_id in hist and "9" in hist[prompt_id].get("outputs", {}):
            img_info = hist[prompt_id]["outputs"]["9"]["images"][0]
            img_resp = req.get(
                f"{server}/view",
                params={"filename": img_info["filename"], "subfolder": img_info.get("subfolder", ""), "type": "output"},
                timeout=30,
            )
            return img_resp.content
        time.sleep(1)

    raise TimeoutError("ComfyUI generation timed out")
