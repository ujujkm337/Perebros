import os
import requests
import json
import time
from flask import Flask, request
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# --- Конфигурация API Кандинского (Fusion Brain) ---
# Ключи берутся из переменных окружения
API_KEY = os.environ.get('KANDINSKY_API_KEY')
SECRET_KEY = os.environ.get('KANDINSKY_SECRET_KEY')
BASE_URL = 'https://api-key.fusionbrain.ai/'
AUTH_HEADERS = {
    'X-Key': f'Key {API_KEY}',
    'X-Secret': f'Secret {SECRET_KEY}'
}

# Эндпоинты API
PIPELINES_URL = BASE_URL + 'key/api/v1/pipelines'
GENERATE_URL = BASE_URL + 'key/api/v1/text2image/run'
STATUS_URL = BASE_URL + 'key/api/v1/pipeline/status/'

# --- Функции помощники ---

def get_pipeline_id():
    """Получает ID пайплайна для запуска генерации."""
    try:
        response = requests.get(PIPELINES_URL, headers=AUTH_HEADERS)
        response.raise_for_status()
        data = response.json()
        # Предполагаем, что нужный ID - первый в списке
        return data[0]['id']
    except Exception as e:
        print(f"Ошибка получения Pipeline ID: {e}")
        return None

def convert_to_rgb565(image_url):
    """Скачивает изображение, конвертирует его в RGB565 и возвращает байты."""
    try:
        # Скачиваем изображение по URL
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Открываем изображение из байтов
        img = Image.open(BytesIO(response.content))
        
        # Обрезаем до 160x128 (или других размеров ESP32)
        # Если Кандинский сгенерировал 512x512, нужно обрезать или ресайзить
        # Предположим, что нужен размер 160x128, как указано в запросе
        img = img.resize((160, 128)) 
        
        # Конвертируем в RGB565 (Pillow использует 'RGB' для 24-бит, затем вручную в 16-бит)
        rgb_img = img.convert('RGB')
        
        rgb565_data = bytearray()
        for y in range(rgb_img.height):
            for x in range(rgb_img.width):
                r, g, b = rgb_img.getpixel((x, y))
                # Конвертация 8-бит RGB (RRRRRRRR GGGGGGGG BBBBBBBB) в 16-бит (RRRRR GGGGGG BBBBB)
                r5 = (r >> 3) & 0x1F
                g6 = (g >> 2) & 0x3F
                b5 = (b >> 3) & 0x1F
                
                # Собираем 16-битное значение: (R5 << 11) | (G6 << 5) | B5
                pixel = (r5 << 11) | (g6 << 5) | b5
                
                # Добавляем младший байт, затем старший байт (Little Endian, типично для ESP32)
                rgb565_data.append(pixel & 0xFF)
                rgb565_data.append(pixel >> 8)
                
        return bytes(rgb565_data)

    except Exception as e:
        print(f"Ошибка обработки или конвертации изображения: {e}")
        return None

# --- Основной роут Flask ---

@app.route('/generate', methods=['GET'])
def generate_and_send_image():
    # Получаем IP-адрес ESP32 из запроса
    esp_ip = request.args.get('ip')
    if not esp_ip:
        return "Ошибка: Не передан IP-адрес ESP32.", 400

    # Проверяем наличие ключей
    if not API_KEY or not SECRET_KEY:
        print("Ошибка: API_KEY или SECRET_KEY не настроены в переменных окружения.")
        return "Ошибка: Ключи API не настроены.", 500

    # 1. Получаем Pipeline ID
    pipeline_id = get_pipeline_id()
    if not pipeline_id:
        return "Ошибка: Не удалось получить ID пайплайна (проверьте ключи).", 500

    # 2. Подготовка и запуск генерации
    prompt = os.environ.get('PROMPT')
    params = {
        "type": "GENERATE",
        "numImages": 1,
        "width": 512, # Используем стандартный размер для быстроты
        "height": 512,
        "generateParams": {
            "query": prompt
        }
    }
    
    data = {
        'pipeline_id': (None, pipeline_id),
        'params': (None, json.dumps(params))
    }
    
    try:
        print(f"[API] Запуск генерации Кандинского для промпта: '{prompt}'")
        # Запрос на запуск генерации
        response = requests.post(GENERATE_URL, headers=AUTH_HEADERS, files=data)
        response.raise_for_status()
        request_id = response.json().get('uuid')

        if not request_id:
             print(f"Ошибка: Не получен UUID. Ответ: {response.json()}")
             return "Ошибка: Не получен ID генерации.", 500

    except Exception as e:
        print(f"[API] Ошибка запуска генерации: {e}")
        return "Ошибка: Не удалось запустить генерацию (проверьте ключи).", 500


    # 3. Опрос статуса
    start_time = time.time()
    file_url = None
    
    # Опрос в течение 120 секунд (запас по таймауту 150с)
    while not file_url and (time.time() - start_time < 120):
        time.sleep(10) # Ждем 10 секунд между проверками

        try:
            status_response = requests.get(STATUS_URL + request_id, headers=AUTH_HEADERS)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status = status_data.get('status')
            
            if status == 'DONE':
                print("[API] Генерация завершена. Скачиваю изображение.")
                files = status_data['result']['files']
                if files:
                    file_url = files[0] # Получаем URL первого файла
                    break
                
            elif status == 'FAIL':
                error_desc = status_data.get('errorDescription', 'Неизвестная ошибка.')
                print(f"[API] Генерация провалена: {error_desc}")
                return f"Ошибка: Генерация провалена: {error_desc}", 500
            
            print(f"[API] Текущий статус: {status}. Прошло времени: {int(time.time() - start_time)}s")

        except Exception as e:
            print(f"[API] Ошибка при проверке статуса: {e}")
            break


    # 4. Обработка таймаута
    if not file_url:
        print("[API] Таймаут: Не удалось получить финальный URL изображения.")
        return "Таймаут: Кандинский не успел сгенерировать изображение.", 500

    
    # 5. Скачивание, конвертация и отправка на ESP32
    print(f"[ESP32] Конвертирую и отправляю изображение на http://{esp_ip}:80/image")
    rgb565_data = convert_to_rgb565(file_url)

    if rgb565_data:
        try:
            # Отправка данных на ESP32
            response = requests.post(f"http://{esp_ip}:80/image", data=rgb565_data, timeout=5)
            response.raise_for_status()
            print("[ESP32] Изображение успешно отправлено.")
            return "Изображение успешно сгенерировано и отправлено.", 200
        except Exception as e:
            print(f"[ESP32] Ошибка отправки на ESP32: {e}")
            return f"Ошибка: Не удалось отправить данные на ESP32 ({e}).", 500
    
    return "Ошибка: Не удалось обработать изображение.", 500

@app.route('/', methods=['GET'])
def home():
    return "Сервер для генерации изображений Кандинского активен. Используйте /generate.", 200
