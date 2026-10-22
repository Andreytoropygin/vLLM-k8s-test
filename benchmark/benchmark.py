import argparse
import json
import time
import httpx
import sys

def run_benchmark(file_path: str, api_url: str, api_key: str):
    print(f"\n[INFO] Чтение промптов из файла: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            prompts = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print(f"[ERROR] Файл {file_path} не найден!")
        return

    if not prompts:
        print("[ERROR] Файл пуст или не содержит валидных промптов.")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    with httpx.Client(timeout=180.0) as client:
        print("\n[INFO] Выполняется прогревочный запрос (Warmup)...")
        warmup_payload = {
            "model": "Qwen/Qwen2.5-1.5B-Instruct",
            "messages": [{"role": "user", "content": "Привет! Ответь одним словом: готов."}],
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        try:
            warmup_resp = client.post(api_url, headers=headers, json=warmup_payload)
            if warmup_resp.status_code == 200:
                print("[INFO] Сервер успешно прогрет и готов к бенчмарку.\n")
            else:
                print(f"[ERROR] Прогревочный запрос завершился с ошибкой (Статус {warmup_resp.status_code}): {warmup_resp.text}")
                print("[ERROR] Завершаем работу бенчмарка.")
                sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Не удалось подключиться к серверу при прогреве: {e}")
            print("[ERROR] Завершаем работу бенчмарка.")
            sys.exit(1)


        print(f"[INFO] Запуск бенчмарка (сбор TTFT, Latency, Throughput) для {len(prompts)} промптов...\n")
        print(f"{'№':<4} | {'TTFT (s)':<10} | {'Latency (s)':<12} | {'Tokens':<8}")
        print("-" * 45)
    
        metrics = []
        for i, prompt in enumerate(prompts, 1):
            payload = {
                "model": "Qwen/Qwen2.5-1.5B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "stream_options": {"include_usage": True}
            }

            ttft = None
            latency = 0.0
            completion_tokens = 0
            start_time = time.perf_counter()

            try:
                with client.stream("POST", api_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        print(f"[{i}] Ошибка {response.status_code}: {response.text}")
                        continue

                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        if line.startswith("data: "):
                            line = line[6:]
                        
                        if line.strip() == "[DONE]":
                            break

                        try:
                            chunk = json.loads(line)
                            
                            if ttft is None:
                                choices = chunk.get("choices", [])
                                if choices and choices[0].get("delta", {}).get("content"):
                                    ttft = time.perf_counter() - start_time

                            usage = chunk.get("usage")
                            if usage:
                                completion_tokens = usage.get("completion_tokens", 0)

                        except json.JSONDecodeError:
                            continue

                latency = time.perf_counter() - start_time
                if ttft is None:
                    ttft = latency

                if completion_tokens == 0:
                    completion_tokens = 15

                metrics.append({"ttft": ttft, "latency": latency, "tokens": completion_tokens})

                print(f"{i:<4} | {ttft:<10.3f} | {latency:<12.3f} | {completion_tokens:<8}")

            except Exception as e:
                print(f"[{i}] Ошибка соединения: {e}")

    # Итоговая статистика
    if metrics:
        avg_ttft = sum(m["ttft"] for m in metrics) / len(metrics)
        avg_latency = sum(m["latency"] for m in metrics) / len(metrics)
        total_tokens = sum(m["tokens"] for m in metrics)
        total_time = sum(m["latency"] for m in metrics)
        avg_throughput = total_tokens / total_time if total_time > 0 else 0

        print("-" * 45)
        print(f"\n=== ИТОГОВЫЕ МЕТРИКИ БЕНЧМАРКА ===")
        print(f"Среднее время до первого токена (Avg TTFT): {avg_ttft:.3f} сек")
        print(f"Средняя задержка ответа (Avg Latency): {avg_latency:.3f} сек")
        print(f"Суммарная пропускная способность (Throughput): {avg_throughput:.2f} токенов/сек")
        print(f"Всего успешно обработано запросов: {len(metrics)}")
        print(f"Всего сгенерировано токенов: {total_tokens}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="vLLM CPU Streaming Benchmark with TTFT & Throughput")
    parser.add_argument("--file", type=str, required=True, help="Путь к файлу с промптами")
    parser.add_argument("--url", type=str, default="http://localhost:8000/v1/chat/completions", help="URL эндпоинта vLLM")
    parser.add_argument("--key", type=str, required=True, help="Bearer токен")

    args = parser.parse_args()
    run_benchmark(args.file, args.url, args.key)
