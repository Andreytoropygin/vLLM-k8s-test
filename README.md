# Инструкция по запуску системы инференса LLM (vLLM + Kubernetes)

Пошаговая инструкция для развертывания отказоустойчивой системы инференса модели `Qwen/Qwen2.5-1.5B-Instruct` на базе **vLLM (CPU)** в локальном кластере **Minikube**.

## Предварительные требования

Убедитесь, что на вашей машине установлены:
* **Docker Desktop** (или Docker Engine)
* **Minikube**
* **kubectl** (со встроенной поддержкой Kustomize)
* **Python 3.10+** (для выполнения нагрузочного тестирования)

---

## Шаг 1. Настройка переменных окружения (Токен Hugging Face)

Для быстрой загрузки модели из репозитория Hugging Face укажите ваш личный токен через защищенный `.env` файл (он автоматически исключен из Git).

1. Скопируйте шаблон конфигурации:
   * **Linux / macOS (Bash):**
      ```bash
      cp k8s/.env.example k8s/.env.secrets
      ```

   * **Windows (PowerShell):**
      ```powershell
      copy k8s\.env.example k8s\.env.secrets
      ```

2. Откройте файл `k8s/.env.secrets` и впишите ваш токен (начинающийся с `hf_...`):
   ```env
   VLLM_API_KEY=ВашКлюч
   HF_TOKEN=hf_ВашНастоящийТокенHuggingFace
   ```

---

## Шаг 2. Запуск кластера Minikube

Запустите локальный кластер Kubernetes с выделением достаточного объема ресурсов (минимум 4 ядра CPU и 8 ГБ RAM):

```powershell
minikube start --driver=docker --cpus=4 --memory=8192 --disk-size=25g
```

Убедитесь, что узел перешел в статус `Ready`:
```powershell
kubectl get nodes
```

---

## Шаг 3. Сборка образов напрямую внутри Minikube

Чтобы не перегружать память хоста через `minikube image load`, используйте встроенный сборщик Minikube, который собирает образы сразу внутри среды выполнения кластера:

1. Сборка образа для инициализации и скачивания модели (`initContainer`):
   ```powershell
   minikube image build -t model-downloader:latest ./docker/downloader
   ```

2. Сборка основного образа сервера vLLM (CPU):
   ```powershell
   minikube image build -t vllm-cpu-custom:latest ./docker/vLLM
   ```

Проверьте наличие собранных образов в системе Minikube:
```powershell
minikube image ls
```

---

## Шаг 4. Деплой приложения в Kubernetes

Примените манифесты из папки `k8s` одной командой (Kustomize автоматически подтянет секреты из `.env.secrets`):

```powershell
kubectl apply -k ./k8s
```

Отслеживайте процесс запуска пода и инициализации (сначала отработает загрузчик в `initContainer`, после чего запустится основной сервер):
```powershell
kubectl get pods -w
```

Вы можете проверить логи каждого контейнера:
* Логи скачивания весов:
  ```powershell
  kubectl logs -l app=vllm-inference -c model-downloader -f
  ```
* Логи сервера vLLM:
  ```powershell
  kubectl logs -l app=vllm-inference -c vllm-server -f
  ```

---

## Шаг 5. Проверка работы API и приватности логов

1. В отдельном окне терминала пробросьте порт сервиса на вашу локальную машину:
   ```powershell
   kubectl port-forward --address 0.0.0.0 svc/vllm-service 8000:8000
   ```

2. Выполните тестовый запрос с помощью нативной утилиты `curl`:

   * **Linux / macOS (Bash):**
     ```bash
     curl http://localhost:8000/v1/chat/completions \
       -H "Content-Type: application/json" \
       -H "Authorization: Bearer ВашКлюч" \
       -d '{
         "model": "Qwen/Qwen2.5-1.5B-Instruct",
         "messages": [{"role": "user", "content": "Назови столицу Франции одним словом."}],
         "max_tokens": 20
       }'
     ```

   * **Windows (PowerShell):**
      ```powershell
      curl.exe -X POST "http://localhost:8000/v1/chat/completions" `
      -H "Content-Type: application/json" `
      -H "Authorization: Bearer safeboard" `
      -d '{\"model\": \"Qwen/Qwen2.5-1.5B-Instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"Назови столицу Франции одним словом.\"}], \"max_tokens\": 20}'
      ```

3. Проверьте логи сервера — вы увидите факт обращения к эндпоинту, но тексты промптов и ответов будут скрыты кастомным фильтром приватности:
   ```powershell
   kubectl logs -l app=vllm-inference -c vllm-server --tail=10
   ```

---

## Шаг 6. Нагрузочное тестирование

Для замера метрик **TTFT**, **Latency** и **Throughput**:

1. Создайте виртуальном окружении:

   * **Linux / macOS (Bash):**
      ```bash
      python3 -m venv venv
      source venv/bin/activate
      ```

   * **Windows (PowerShell):**
      ```powershell
      python -m venv venv
      .\venv\Scripts\Activate.ps1
      ```

2. Установите зависимости:
   ```bash
   pip install -r benchmark/requirements.txt
   ```
   
4. Убедитесь, что `kubectl port-forward` активен, и запустите скрипт, указав путь к файлу с промптами и Ваш API-ключ. В папке уже `benchmark` есть 2 набора промптов для тестирвоания:

   * `prompts_short.txt` - 50 коротких промптов

   * `prompts_long.txt` - 10 длинных промптов

   ```bash
   python benchmark/benchmark.py --file benchmark/prompts_short.txt --key ВашКлюч
   python benchmark/benchmark.py --file benchmark/prompts_long.txt --key ВашКлюч
   ```

# Результаты нагрузочного тестирования (Бенчмарк)

Тестирование проводилось для модели **`Qwen/Qwen2.5-1.5B-Instruct`** на CPU в локальном кластере Minikube (4 vCPU, 8 ГБ RAM) и со следующими параметрами (k8s/configmap.yaml):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vllm-config
data:
  MODEL_ID: "Qwen/Qwen2.5-1.5B-Instruct"
  MODEL_DIR: "/models/Qwen2.5-1.5B-Instruct"
  DTYPE: "bfloat16"
  MAX_MODEL_LEN: "1024"
  PORT: "8000"
  VLLM_CPU_KVCACHE_SPACE: "1"
  OMP_NUM_THREADS: "2"
```

Для тестирования были использованы 2 набора коротких и длинных промптов, содержащихся в файлах `prompts_short.txt` и `prompts_long.txt` соответственно.

### Сводная таблица метрик

| Тип нагрузки | Кол-во запросов | Avg TTFT (сек) | Avg Latency (сек) | Средняя длина ответа (токенов) | Throughput (токенов/сек) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Короткие промпты** | 50 | 2.462 | 9.101| ~50 | 5.52 |
| **Длинные промпты** | 10 | 2.887 | 51.625| ~363 | 7.02 |

---

### Анализ результатов

* **Время до первого токена (TTFT):** На коротких запросах стадия чтения промпта занимает почти на полсекунды меньше, чем на длинных. В масштабе 2-3 секунд это почти незаметно. Стабильный показатель TTFT на всех запросах подтверждает отсутствие переполнения памяти и предсказуемую работу механизма внимания на CPU.
* **Общая задержка (Latency):** Практически линейно зависит от объема генерируемого текста. 
* **Пропускная способность (Throughput):** При генерации длинных ответов итоговая пропускная способность оказалась выше. Это объясняется тем, что при генерации коротких ответов модель проводит большую долю времени на стадии чтения промпта токены, не выдавая токенов.

### Оптимизация Throughput

В текущей конфигурации контейнер работает на пределе выделенного лимита оперативной памяти (`VLLM_CPU_KVCACHE_SPACE: "1"`), а вычисления ограничены двумя потоками (`OMP_NUM_THREADS: "2"`). Базовый шаг для роста производительности в любом сценарии — увеличить `OMP_NUM_THREADS` до числа физических ядер CPU и включить привязку потоков (`VLLM_CPU_OMP_THREADS_BIND: "auto"`). 

Параметры, требующие расширения памяти, дадут эффект только при пропорциональном увеличении ресурсов пода (RAM Limits).

#### А) Большой поток коротких запросов 
Главная цель — плотнее упаковать мелкие запросы в текущий объем памяти и ускорить их совместную обработку:
* Снизить `MAX_MODEL_LEN` и уменьшить `--block-size` (до `16`): это позволит разместить больше коротких запросов в том же 1 ГБ кэша.
* Увеличить `--max-num-seqs`: позволит объединять больше легких запросов в один батч за такт вычислений.
* Включить `--enable-prefix-caching`: избавит CPU от повторного пересчета одинаковых системных промптов и шаблонов чата (но в моем бенчмарке их нет, поэтому прироста на нем не будет).

#### Б) Меньше запросов, но огромный контекст
Главная цель — ускорить фазу чтения промпта и избежать вытеснения данных из KV-кэша:
* Включить `--enable-chunked-prefill` и настроить `--max-num-batched-tokens`: разобьет обработку длинных промптов на части, чтобы один тяжелый запрос не блокировал генерацию токенов для остальных.
* Снизить `--max-num-seqs` (до `2`–`4`):* предотвратит переполнение кэша и принудительный пересчет контекста.
* Увеличить `VLLM_CPU_KVCACHE_SPACE` (до `4`+ ГБ) и `MAX_MODEL_LEN` (до `4096`+): применимо только при выделении контейнеру дополнительных ресурсов, так как хранение длинного контекста напрямую упирается в физический размер кэша.