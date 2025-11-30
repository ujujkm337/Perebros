from flask import Flask, request
import requests
import os 
from flask_cors import CORS # Добавляем CORS для совместимости

app = Flask(__name__)
CORS(app) # Включаем CORS для всех источников

# КОНФИГУРАЦИЯ БЕСПЛАТНОГО API mlvoca.com
API_URL = "https://mlvoca.com/api/generate"
MODEL_NAME = "tinyllama" 

@app.route('/ask', methods=['POST'])
def ask_llm():
    """
    Принимает HTTP-запрос от ESP32 и перенаправляет его по HTTPS в mlvoca.com.
    """
    try:
        # 1. Получаем prompt от ESP32 
        data = request.json
        prompt = data.get('prompt', 'Give me a fun fact about Python.')
        
        # 2. Формируем payload для mlvoca.com
        mlvoca_payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False # Запрашиваем полный ответ
        }

        # 3. Отправляем запрос в mlvoca.com (Render делает HTTPS-запрос)
        response = requests.post(
            API_URL, 
            json=mlvoca_payload, 
            timeout=40 # Увеличиваем таймаут на всякий случай
        )
        
        # 4. Проверяем статус ответа
        if response.status_code == 200:
            result_json = response.json()
            if 'response' in result_json:
                # Возвращаем ESP32 только чистый текст (без JSON), чтобы упростить чтение
                return result_json['response'], 200, {'Content-Type': 'text/plain'} 
            else:
                return "LLM API Error: No response field in result.", 500
        else:
            # Возвращаем ошибку, полученную от mlvoca.com
            return f"LLM Server Error: Status {response.status_code}", 500

    except Exception as e:
        # Ошибка на сервере Render
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    # Используем переменную окружения PORT для Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
