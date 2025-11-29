from flask import Flask, request
import requests
import os # Необходимо для получения порта

app = Flask(__name__)

# КОНФИГУРАЦИЯ БЕСПЛАТНОГО API mlvoca.com
API_URL = "https://mlvoca.com/api/generate"
MODEL_NAME = "tinyllama" 
# Используем TinyLlama, так как она самая быстрая и легкая

@app.route('/ask', methods=['POST'])
def ask_llm():
    try:
        # 1. Получаем prompt от ESP32 (он отправляет только текст вопроса)
        data = request.json
        prompt = data.get('prompt', 'Give me a fact about MicroPython.')
        
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
            timeout=30 # Даем 30 секунд на ответ
        )
        
        # 4. Проверяем статус от mlvoca.com
        if response.status_code == 200:
            result_json = response.json()
            if 'response' in result_json:
                # Возвращаем ESP32 только чистый текст (без JSON), чтобы он легко его прочитал
                return result_json['response'], 200, {'Content-Type': 'text/plain'} 
            else:
                return "LLM API Error: No response field in result.", 500
        else:
            return f"LLM Server Error: Status {response.status_code}", 500

    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    # Render использует переменную окружения PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
