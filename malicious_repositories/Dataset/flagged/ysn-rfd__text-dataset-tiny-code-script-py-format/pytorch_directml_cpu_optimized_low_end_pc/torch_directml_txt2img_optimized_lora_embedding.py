"""
Complete Python code for CPU-optimized Stable Diffusion with LoRA & Embeddings support
All key techniques for systems with limited RAM
Code By: YSNRFD
Telegram: @ysnrfd
Github: ysnrfd
Huggingface: ysnrfd
"""

import torch
from diffusers import StableDiffusionPipeline, LCMScheduler
import time
import random
import gc
import os
import psutil
from tqdm import tqdm
from safetensors.torch import load_file as load_safetensors
import warnings

# Ignore non-critical warnings
warnings.filterwarnings("ignore", category=UserWarning)

def setup_cpu_memory_optimizations(pipe):
    """
    Apply all memory reduction methods specifically optimized for CPU usage
    """
    print("\n" + "="*60)
    print("Applying CPU-specific memory reduction methods")
    print("="*60)
    
    # 1. 8-bit Quantization
    print("Performing 8-bit Quantization for CPU...")
    pipe.unet = torch.quantization.quantize_dynamic(
        pipe.unet, {torch.nn.Linear, torch.nn.Conv2d}, dtype=torch.qint8
    )
    pipe.vae = torch.quantization.quantize_dynamic(
        pipe.vae, {torch.nn.Linear, torch.nn.Conv2d}, dtype=torch.qint8
    )
    pipe.text_encoder = torch.quantization.quantize_dynamic(
        pipe.text_encoder, {torch.nn.Linear}, dtype=torch.qint8
    )
    print("UNet, VAE, and Text Encoder quantized to 8-bit")

    # 2. Attention Slicing
    print("\nEnabling Attention Slicing...")
    pipe.enable_attention_slicing("max")

    # 3. VAE Slicing
    print("\nEnabling VAE Slicing...")
    pipe.vae.enable_slicing()

    # 4. CPU thread settings
    cpu_cores = max(1, os.cpu_count() // 2)
    torch.set_num_threads(cpu_cores)
    torch.set_num_interop_threads(1)
    print(f"CPU threads set to: {cpu_cores}")

    # 5. Disable CUDA backend (CPU only)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    print("\n" + "="*60)
    print("All CPU memory reduction methods applied")
    print("="*60)
    return pipe


def load_lora_weights(pipe, lora_path, alpha=1.0):
    """Load LoRA safely, filtering unsupported keys."""
    if not os.path.exists(lora_path):
        print(f"[LoRA] File not found: {lora_path}")
        return False

    print(f"\nLoading LoRA: {lora_path}")
    try:
        # بارگذاری فایل LoRA
        if lora_path.endswith(".safetensors"):
            state_dict = load_safetensors(lora_path)
        else:
            state_dict = torch.load(lora_path, map_location="cpu")

        # فیلتر کردن کلیدهای معتبر LoRA
        unet_state_dict = {}
        te_state_dict = {}

        for key in state_dict.keys():
            # حذف کلیدهای غیرضروری
            if "scale" in key or "alpha" in key or "time_embedding" in key:
                continue  # این کلیدها را نادیده بگیر

            if "lora_unet_" in key:
                new_key = key.replace("lora_unet_", "").replace("_lora", "")
                unet_state_dict[new_key] = state_dict[key] * alpha
            elif "lora_te_" in key:
                new_key = key.replace("lora_te_", "").replace("_lora", "")
                te_state_dict[new_key] = state_dict[key] * alpha

        # اعمال LoRA به UNet
        if unet_state_dict:
            print(f"  Applying LoRA to UNet ({len(unet_state_dict)} weights)...")
            missing, unexpected = pipe.unet.load_state_dict(unet_state_dict, strict=False)
            if missing:
                print(f"    Missing in model: {len(missing)}")
            if unexpected:
                print(f"    Unexpected in LoRA: {len(unexpected)}")

        # اعمال LoRA به Text Encoder
        if te_state_dict:
            print(f"  Applying LoRA to Text Encoder ({len(te_state_dict)} weights)...")
            missing, unexpected = pipe.text_encoder.load_state_dict(te_state_dict, strict=False)
            if missing:
                print(f"    Missing in model: {len(missing)}")
            if unexpected:
                print(f"    Unexpected in LoRA: {len(unexpected)}")

        # پاک‌سازی حافظه
        del state_dict, unet_state_dict, te_state_dict
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

        print(f"✅ LoRA loaded successfully (alpha={alpha})")
        return True

    except Exception as e:
        print(f"[LoRA] Error during loading: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def load_textual_inversion_embeddings(pipe, embedding_path):
    """Load Textual Inversion Embedding (token added to tokenizer)"""
    if not os.path.exists(embedding_path):
        print(f"[Embedding] File not found: {embedding_path}")
        return False

    print(f"\nLoading Textual Inversion Embedding: {embedding_path}")
    try:
        if embedding_path.endswith(".safetensors"):
            data = load_safetensors(embedding_path)
        else:
            data = torch.load(embedding_path, map_location="cpu")

        # Extract token and embedding
        if "string_to_param" in data:
            # New format
            for token, embedding in data["string_to_param"].items():
                embedding = embedding.detach().cpu()
        else:
            # Old format: assume first tensor is embedding
            keys = list(data.keys())
            token = keys[0].replace(" ", "") if keys else "CUSTOM"
            embedding = data[keys[0]].detach().cpu()

        # Resize token embeddings
        tokenizer = pipe.tokenizer
        text_encoder = pipe.text_encoder

        # Add token
        num_added_tokens = tokenizer.add_tokens(token)
        if num_added_tokens == 0:
            print(f"Token {token} already exists, reusing slot.")
        else:
            print(f"Added new token: {token}")

        # Resize text encoder embeddings
        text_encoder.resize_token_embeddings(len(tokenizer))

        # Get token ID
        token_id = tokenizer.convert_tokens_to_ids(token)
        text_encoder.get_input_embeddings().weight.data[token_id] = embedding

        print(f"Embedding '{token}' loaded successfully.")
        del data, embedding
        gc.collect()
        return token
    except Exception as e:
        print(f"[Embedding] Error loading: {str(e)}")
        return False


def verify_memory_usage():
    """Check memory usage using psutil"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"Process memory usage: {memory_info.rss / (1024**3):.2f} GB")
        virtual_memory = psutil.virtual_memory()
        print(f"System available: {virtual_memory.available / (1024**3):.2f} GB")
        print(f"Memory usage: {virtual_memory.percent:.1f}%")
    except Exception as e:
        print(f"Memory verification error: {e}")


def check_system_resources():
    """Check minimum resources"""
    virtual_memory = psutil.virtual_memory()
    available_gb = virtual_memory.available / (1024**3)
    cpu_cores = os.cpu_count()

    print(f"Sufficient memory available: {available_gb:.2f} GB")
    print(f"Detected CPU cores: {cpu_cores}")

    return available_gb >= 1.5


def generate_random_seed():
    return random.randint(0, 1000000000)


def generate_image_with_cpu_optimizations(pipe, prompt, negative_prompt=""):
    """Generate image with full optimizations and LoRA/Embedding support"""
    print("\n" + "="*60)
    print(f"Generating image: '{prompt}'")
    print("="*60)

    generation_settings = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": 512,
        "height": 512,
        "num_inference_steps": 10,
        "guidance_scale": 1.0,
        "output_type": "pil",
        "generator": torch.Generator(device="cpu").manual_seed(generate_random_seed())
    }

    print("Settings:")
    for k, v in generation_settings.items():
        if k != "generator":
            print(f" - {k}: {v}")

    gc.collect()
    verify_memory_usage()

    print("\nStarting generation...")
    start_time = time.time()
    try:
        progress_bar = tqdm(total=generation_settings["num_inference_steps"], desc="Processing")
        output = pipe(**generation_settings)
        image = output.images[0]
        progress_bar.update(generation_settings["num_inference_steps"])
        progress_bar.close()

        timestamp = int(time.time())
        seed = generation_settings["generator"].initial_seed()
        output_path = f"output_{timestamp}_{seed}.png"
        image.save(output_path)

        elapsed = time.time() - start_time
        print(f"\n✅ Image saved: {output_path}")
        print(f"⏱ Time: {elapsed:.2f} seconds")
        verify_memory_usage()
        return image
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print("\n❌ Memory error! Try:")
            print("   - Reduce image size (e.g., 384x384)")
            print("   - Close other apps")
            print("   - Use a smaller base model")
        else:
            print(f"❌ Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def main():
    print("="*60)
    print("CPU-Optimized Stable Diffusion with LoRA & Embeddings")
    print("="*60)

    if not check_system_resources():
        print("⚠️ Low memory. Continue? (y/n)")
        if input().lower() != 'y':
            return

    device = torch.device("cpu")
    print(f"Running on: {device}")

    # 1. Load base model
    default_model = "ds_lcm.safetensors"
    print(f"Default model: {default_model}")
    model_path = input("Enter model path (or press Enter for default): ").strip()
    if not model_path:
        model_path = default_model

    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return

    try:
        print("Loading base model...")
        pipe = StableDiffusionPipeline.from_single_file(
            model_path,
            torch_dtype=torch.float32,
            use_safetensors=True,
            safety_checker=None,
            requires_safety_checker=False
        )
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
        pipe = pipe.to(device)
        print("✅ Base model loaded.")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    # 2. Apply CPU optimizations
    pipe = setup_cpu_memory_optimizations(pipe)

    # 3. Load LoRA (optional)
    print("\n" + "="*60)
    print("LoRA Support")
    print("="*60)
    lora_path = input("Enter LoRA path (or press Enter to skip): ").strip()
    if lora_path and os.path.exists(lora_path):
        alpha = input("Enter LoRA weight (0.1–1.0, default 0.75): ").strip()
        alpha = float(alpha) if alpha.replace('.', '').isdigit() else 0.75
        load_lora_weights(pipe, lora_path, alpha=alpha)

    # 4. Load Embedding (optional)
    print("\n" + "="*60)
    print("Textual Inversion Embedding Support")
    print("="*60)
    emb_path = input("Enter embedding path (or press Enter to skip): ").strip()
    embedding_token = None
    if emb_path and os.path.exists(emb_path):
        result = load_textual_inversion_embeddings(pipe, emb_path)
        if isinstance(result, str):
            embedding_token = result

    # 5. Prompt input
    print("\n" + "="*60)
    print("Prompt Input")
    print("="*60)
    default_prompt = "A beautiful landscape with mountains and a lake, ultra-detailed, realistic, 4k"
    user_prompt = input(f"Enter prompt (or press Enter for default):\n{default_prompt}\n> ").strip()
    if not user_prompt:
        user_prompt = default_prompt

    # Add embedding token to prompt if loaded
    if embedding_token:
        user_prompt = f"{embedding_token}, {user_prompt}"
        print(f"Using embedding token in prompt: {user_prompt}")

    neg_prompt = input("Enter negative prompt (optional): ").strip()

    # 6. Generate
    generate_image_with_cpu_optimizations(pipe, user_prompt, neg_prompt)

    # 7. Cleanup
    print("\nCleaning up...")
    del pipe
    gc.collect()
    print("✅ Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
        gc.collect()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")