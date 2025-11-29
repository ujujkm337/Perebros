import os
import requests
from flask import Flask, request, jsonify

# Инициализация Flask приложения
app = Flask(__name__)

# --- ВАШ КЛЮЧ API GEMINI ---
# Рекомендуется хранить ключ в переменных окружения Render, 
# но для простоты мы оставим его в коде.
GEMINI_API_KEY = "AIzaSyAnmIxt6lrfNsoUKa2YKaX-_9G7QASD9wM"
# ----------------------------

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

@app.route('/', methods=['GET'])
def home():
    """Простая проверка работоспособности сервера."""
    return "Gemini Proxy is running!"

@app.route('/ask', methods=['POST'])
def ask_gemini():
    """
    Основная функция: принимает prompt от ESP32 и отправляет его в Gemini.
    """
    # 1. Получаем PROMPT из JSON-тела запроса от ESP32
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({"error": "Missing 'prompt' in request body"}), 400
        
        prompt = data['prompt']
    except Exception as e:
        return jsonify({"error": f"Invalid JSON or request: {e}"}), 400

    # 2. Формируем тело запроса для Gemini API
    gemini_payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    # 3. Отправляем запрос в Gemini
    try:
        response = requests.post(
            GEMINI_URL,
            headers={'Content-Type': 'application/json'},
            json=gemini_payload
        )
        
        # Если Gemini вернул ошибку (например, 400), передаем ее дальше
        response.raise_for_status() 
        
        gemini_response = response.json()
        
        # 4. Извлекаем чистый текст ответа
        text = gemini_response['candidates'][0]['content']['parts'][0]['text']
        
        # 5. Возвращаем ответ ESP32 в простом текстовом формате
        return text, 200

    except requests.exceptions.HTTPError as errh:
        return jsonify({"error": f"HTTP Error from Gemini: {errh}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Internal Error: {e}"}), 500

if __name__ == '__main__':
    # Render использует переменную окружения PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
