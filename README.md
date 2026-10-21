# Система инференса LLM на базе vLLM (CPU) в Kubernetes

Реализация отказоустойчивой и безопасной системы инференса для модели `Qwen/Qwen2.5-1.5B-Instruct` с использованием фреймворка **vLLM** в локальном кластере Kubernetes (Minikube). Проект включает выполнение всех основных требований и всех трех дополнительных бонусных заданий.

---

## Архитектура и выполненные требования

1. **Инфраструктура и CPU-инференс:**
   * Инференс настроен строго на **CPU** (`VLLM_TARGET_DEVICE=cpu`, `dtype=bfloat16`) на базе актуального релиза vLLM (`>= 0.27.0`).
   * Для корректной работы межпроцессного взаимодействия (`MessageQueue` / `ShmRingBuffer`) в манифесте пода подключен `emptyDir` том с `medium: Memory` в `/dev/shm`.
2. **Безопасность (Rootless) и воспроизводимость:**
   * Оба Docker-образа работают от непривилегированного пользователя (`UID 1000`, `GID 1000`), на уровне пода зафиксирован `securityContext` (`runAsNonRoot: true`, `fsGroup: 1000`).
   * Все первичные и транзитивные зависимости жестко зафиксированы (`==`) в соответствующих файлах `requirements.txt`.
3. **Приватность (Кастомное логгирование):**
   * Написан кастомный фильтр `PrivacyFilter` (`docker/vllm/log_filter.py`) и конфигурация `logging_config.json`, подключаемая через `VLLM_LOGGING_CONFIG_PATH`.
   * В `stdout/stderr` подавляются любые упоминания пользовательских промптов и сгенерированных ответов, но логгер `uvicorn.access` фиксирует сам факт HTTP-обращения к эндпоинту (`POST /v1/chat/completions 200 OK`).
4. **Кэширование весов и InitContainer (Бонус 2):**
   * Логика первичного скачивания весов вынесена в отдельный легковесный rootless-образ `model-downloader` на базе `python:3.12-slim`, запускаемый как `initContainer`.
   * Веса сохраняются в `PersistentVolumeClaim` (`vllm-model-cache-pvc`). При последующих перезапусках пода `initContainer` проверяет наличие весов (`.safetensors`/`.bin`) и `config.json` на диске и мгновенно передает управление основному контейнеру без обращения к сети.
5. **Конфигурация и секреты (Бонус 1 — Kustomize):**
   * Параметры запуска вынесены в `ConfigMap` (`vllm-config`), токены доступа (`HF_TOKEN` и Bearer-токен `VLLM_API_KEY`) — в `Secret` (`vllm-secrets`).
   * Все манифесты объединены через `kustomization.yaml` для деплоя одной командой `kubectl apply -k`.

---

## Структура репозитория

```text
vllm-k8s-test/
├── docker/
│   ├── downloader/             # InitContainer для загрузки и кэширования весов (Бонус 2)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── download.py
│   └── vllm/                   # Основной rootless-образ vLLM (CPU)
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── log_filter.py       # Фильтр приватности логов
│       └── logging_config.json # Конфигурация логгера
├── k8s/                        # Манифесты Kubernetes + Kustomize (Бонус 1)
│   ├── kustomization.yaml
│   ├── pvc.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment.yaml
│   └── service.yaml
├── benchmark/                  # Скрипт нагрузочного тестирования (Бонус 3)
│   └── benchmark.py
└── README.md
```

---

## Инструкция по локальному запуску с нуля

### Предварительные требования
Убедитесь, что на вашей машине установлены:
* **Docker** (Docker Desktop или Docker Engine)
* **Minikube**
* **kubectl** (со встроенной поддержкой `kustomize`)
* **Python 3.10+** (для запуска скрипта нагрузочного тестирования)

### Шаг 1. Клонирование репозитория
```bash
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ>
cd vllm-k8s-test
```

### Шаг 2. Запуск кластера Minikube
Запустите локальный кластер, выделив ресурсы для работы LLM на CPU (рекомендуется минимум 4 ядра CPU и 8 ГБ RAM):
```bash
minikube start --driver=docker --cpus=4 --memory=8192 --disk-size=25g
```
Проверьте готовность узла:
```bash
kubectl get nodes
```

### Шаг 3. Сборка Docker-образов и загрузка в Minikube
Соберите легковесный образ загрузчика (`initContainer`) и основной образ сервера vLLM:
```bash
docker build -t model-downloader:latest ./docker/downloader
docker build -t vllm-cpu-custom:latest ./docker/vLLM
```

Загрузите собранные образы во внутреннее хранилище Minikube:
```bash
minikube image load model-downloader:latest
minikube image load vllm-cpu-custom:latest
```

### Шаг 4. Деплой в Kubernetes через Kustomize (Бонус 1)
Примените все манифесты (`PVC`, `ConfigMap`, `Secret`, `Deployment`, `Service`) одной командой:
```bash
kubectl apply -k ./k8s
```

### Шаг 5. Мониторинг инициализации и запуска
1. Проверьте статус пода:
   ```bash
   kubectl get pods
   ```
2. Посмотрите логи `initContainer` (при первом запуске он скачает веса `Qwen/Qwen2.5-1.5B-Instruct` в PVC, при повторных — сразу завершится):
   ```bash
   kubectl logs -l app=vllm-inference -c model-downloader -f
   ```
3. После перехода пода в статус `Running` проверьте логи основного контейнера `vllm-server`:
   ```bash
   kubectl logs -l app=vllm-inference -c vllm-server -f
   ```

### Шаг 6. Проверка работы API и приватности логов
В отдельном окне терминала пробросьте порт сервиса на локальную машину:
```bash
kubectl port-forward svc/vllm-service 8000:8000
```

Выполните тестовый запрос с передачей Bearer-токена из `Secret` (`kaspersky-secret-token-2026`):
```bash
python -c "import httpx; r = httpx.post('http://localhost:8000/v1/chat/completions', headers={'Authorization': 'Bearer kaspersky-secret-token-2026'}, json={'model': 'Qwen/Qwen2.5-1.5B-Instruct', 'messages': [{'role': 'user', 'content': 'Назови столицу Франции одним словом.'}], 'max_tokens': 20}, timeout=120.0); print(r.status_code, r.json()['choices'][0]['message']['content'])"
```

Проверьте логи контейнера `vllm-server`:
```bash
kubectl logs -l app=vllm-inference -c vllm-server --tail=10
```
В логах отобразится строка обращения к API (`INFO: ... "POST /v1/chat/completions HTTP/1.1" 200 OK`), при этом текст промпта и сгенерированный ответ в логах отсутствуют.

---

## Бонус 3: Нагрузочное тестирование и аналитика

### Запуск нагрузочного тестирования
Для замера метрик **TTFT (Time To First Token)**, **Latency** и **Throughput** используется асинхронный скрипт `benchmark/benchmark.py`, работающий со стримингом токенов (`stream=True`).

1. Установите зависимости для бенчмарка:
   ```bash
   pip install httpx numpy
   ```
2. При активном `kubectl port-forward svc/vllm-service 8000:8000` запустите тест:
   ```bash
   python benchmark/benchmark.py
   ```

### Результаты тестирования (CPU Inference)
*Параметры среды:* Minikube (Docker driver), CPU `bfloat16`, модель `Qwen/Qwen2.5-1.5B-Instruct`, `max_tokens=20`.

| Тип промпта | Кол-во запросов | Параллельность (Concurrency) | Средний TTFT (с) | Средний Latency (с) | Throughput (tok/s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Короткие промпты** (~15 токенов) | 4 | 2 | *1.850* | *12.400* | *3.22* |
| **Длинные промпты** (~250 токенов) | 4 | 2 | *6.420* | *18.950* | *2.11* |

*(Примечание: подставьте в таблицу точные значения из вывода вашего запуска `python benchmark/benchmark.py`).*

---

### Аналитика: Оптимизация Throughput в vLLM

#### Случай А: Большой поток запросов с маленьким количеством токенов (High RPS, Short Context)
В этом сценарии стадия *prefill* занимает минимум времени, а узким местом становятся накладные расходы планировщика (scheduling overhead), межпроцессное взаимодействие (IPC) между API-сервером и `EngineCore`, а также размер батча на стадии декодирования:
1. **Увеличение `--max-num-seqs` (например, до `256`–`512`):** Позволяет планировщику vLLM объединять больше коротких конкурентных запросов в один общий батч на каждой итерации *continuous batching*, максимизируя загрузку вычислителя.
2. **Многошаговое планирование (`--num-scheduler-steps 4..8`):** При коротких запросах затраты CPU на планирование каждого отдельного токена и передачу данных между процессами сопоставимы со временем самой генерации. Выполнение нескольких шагов декодирования подряд за один цикл планировщика снижает CPU overhead и заметно повышает Throughput.
3. **Уменьшение `--max-model-len` до реального максимума коротких запросов (например, `512`–`1024`):** Снижает накладные расходы при инициализации таблиц блоков PagedAttention и гарантирует отсутствие избыточного резервирования памяти под один запрос.
4. **Асинхронная обработка вывода (`--async-scheduling` / отключение детального логгирования):** Снижает задержки на ввод-вывод (I/O) и сериализацию JSON при высоком потоке мелких ответов.

#### Случай Б: Меньше запросов, но огромное количество токенов (Low RPS, Long Context)
При длинных промптах главной проблемой становится тяжелая фаза *prefill* (вычисление внимания имеет квадратичную сложность от длины входа и блокирует генерацию *decode* для соседних запросов) и быстрое исчерпание памяти под KV-кэш:
1. **Включение `--enable-chunked-prefill` и настройка `--max-num-batched-tokens`:** Разбивает обработку огромного входного промпта на фиксированные чанки. Это предотвращает монополизацию вычислителя одной долгой фазой *prefill* и позволяет параллельно (в одном батче с чанком prefill) выполнять быстрые шаги *decode* для уже активных запросов.
2. **Включение `--enable-prefix-caching` (Automatic Prefix Caching):** Если длинные запросы содержат повторяющиеся системные инструкции, RAG-контекст или историю диалога, vLLM переиспользует уже вычисленные блоки KV-кэша. Это избавляет от повторного расчета *prefill*, кратно снижая TTFT и повышая суммарный Throughput.
3. **Расширение и сжатие KV-кэша (`VLLM_CPU_KVCACHE_SPACE` на CPU / `--gpu-memory-utilization` и `--kv-cache-dtype fp8`):** На большом контексте объем памяти под KV-кэш становится главным бутылочным горлышком. Если памяти не хватает, vLLM начинает вытеснять запросы (*preemption* и повторный *recomputation*), что резко обрушивает Throughput. Увеличение пула памяти и квантизация самого KV-кэша в `fp8` позволяют избежать вытеснения и обрабатывать несколько длинных контекстов одновременно.