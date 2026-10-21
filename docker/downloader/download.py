import os
import sys
import time
import glob
from huggingface_hub import snapshot_download, HfApi

MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
MODEL_DIR = os.getenv("MODEL_DIR", "/models/Qwen2.5-1.5B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None


def is_model_downloaded(directory: str) -> bool:
    """Проверяет, что скачан и конфиг, и сами файлы весов модели."""
    config_exists = os.path.exists(os.path.join(directory, "config.json"))
    weights = (
        glob.glob(os.path.join(directory, "*.safetensors"))
        + glob.glob(os.path.join(directory, "*.bin"))
    )
    incomplete = glob.glob(os.path.join(directory, "**", "*.incomplete"), recursive=True)
    return config_exists and len(weights) > 0 and len(incomplete) == 0


def main():
    if is_model_downloaded(MODEL_DIR):
        print(f"[INFO] Модель и веса уже найдены в {MODEL_DIR}. Пропуск скачивания.")
        sys.exit(0)

    print(f"[INFO] Скачивание полной модели {MODEL_ID} в {MODEL_DIR}...")
    api = HfApi(token=HF_TOKEN)

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            api.model_info(repo_id=MODEL_ID)

            snapshot_download(
                repo_id=MODEL_ID,
                local_dir=MODEL_DIR,
                token=HF_TOKEN,
                max_workers=2,
            )

            if not is_model_downloaded(MODEL_DIR):
                raise RuntimeError(
                    f"snapshot_download завершился, но файлы весов в {MODEL_DIR} отсутствуют (возможно, сбой сети)."
                )

            print("[INFO] Загрузка всех весов успешно завершена.")
            sys.exit(0)

        except Exception as e:
            print(f"[WARN] Попытка {attempt}/{max_retries} не удалась: {e}")
            if attempt < max_retries:
                print("[INFO] Повторная попытка через 10 секунд...")
                time.sleep(10)

    print("[ERROR] Не удалось скачать модель после всех попыток.")
    sys.exit(1)


if __name__ == "__main__":
    main()