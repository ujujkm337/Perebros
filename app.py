from flask import Flask, request
import requests
import os 
from flask_cors import CORS 

app = Flask(__name__)
CORS(app) 

# КОНФИГУРАЦИЯ БЕСПЛАТНОГО API mlvoca.com
API_URL = "https://mlvoca.com/api/generate"
MODEL_NAME = "tinyllama" 

@app.route('/ask', methods=['POST'])
def ask_llm():
    """
    Принимает HTTPS-запрос от ESP32 и перенаправляет его по HTTPS в mlvoca.com.
    """
    try:
        # 1. Получаем prompt от ESP32 
        data = request.get_json(force=True) # Использование force=True для уверенности
        prompt = data.get('prompt', 'Give me a fun fact about Python.')
        
        # 2. Формируем payload для mlvoca.com
        mlvoca_payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False 
        }

        # 3. Отправляем запрос в mlvoca.com
        # ВАЖНО: Увеличиваем таймаут и добавляем заголовок 'connection: close'
        response = requests.post(
            API_URL, 
            json=mlvoca_payload, 
            timeout=60, # Таймаут 60 секунд 
            headers={"connection": "close"}
        )
        
        # 4. Обработка ответа
        if response.status_code == 200:
            result_json = response.json()
            if 'response' in result_json:
                # Возвращаем ESP32 чистый текст
                return result_json['response'], 200
            else:
                return "LLM API Error: No 'response' field in result.", 500
        else:
            # Возвращаем ошибку, полученную от mlvoca.com
            return f"LLM Server Error: Status {response.status_code}", 500

    except Exception as e:
        # Ошибка на сервере Render
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
