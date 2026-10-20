import os
import sys
import glob
from huggingface_hub import snapshot_download

MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
MODEL_DIR = os.getenv("MODEL_DIR", "/models/Qwen2.5-1.5B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

def is_model_downloaded(directory: str) -> bool:
    config_exists = os.path.exists(os.path.join(directory, "config.json"))
    weights = glob.glob(os.path.join(directory, "*.safetensors")) + glob.glob(os.path.join(directory, "*.bin"))
    return config_exists and len(weights) > 0

def main():
    if is_model_downloaded(MODEL_DIR):
        print(f"[INFO] Модель и веса (.safetensors/.bin) уже найдены в {MODEL_DIR}. Пропуск скачивания.")
        sys.exit(0)

    print(f"[INFO] Скачивание полной модели {MODEL_ID} в {MODEL_DIR}...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=MODEL_DIR,
        token=HF_TOKEN if HF_TOKEN else None,
    )
    print("[INFO] Загрузка всех весов успешно завершена.")

if __name__ == "__main__":
    main()