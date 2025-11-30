import os
import requests
import io
import time
import struct
from PIL import Image
from flask import Flask, send_file, abort

app = Flask(__name__)

# --- CHITAYEM KONFIGURATSIYU IZ PEREMENNYKH OKRUZHENIYA RENDER ---
# Render avtomaticheski sozdast eti peremennyye v p. 1.2
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# Proverka na nalichiye promta, inache ispol'zuyem standartnyy
PROMPT = os.environ.get("PROMPT", "сгенерируй кошку в реалистичном стиле, 128x160") 
# --- CHITAYEM KONFIGURATSIYU IZ PEREMENNYKH OKRUZHENIYA RENDER ---

@app.route('/generate', methods=['GET'])
def generate_and_send_image():
    
    # Proverka na nalichiye klyuchey
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "FATAL: Missing configuration keys.", 500

    print(f"[{time.strftime('%H:%M:%S')}] Poluchen zapros ot ESP32. Zapuskayu generatsiyu...")
    
    # 1. OT-PRAVKA KOMANDY V TELEGRAM
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': PROMPT}
        )
    except Exception as e:
        print(f"Oshibka pri ot-pravke v Telegram: {e}")
        return "Telegram Error", 500

    # 2. OZHIDANIYE I POLUCHENIYE IZOBRAZHENIYA
    file_url = None
    start_time = time.time()
    
    while not file_url and (time.time() - start_time < 90): # Taymaut 90 sekund
        time.sleep(3) 
        
        updates = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-1").json()
        
        if updates['ok'] and updates['result']:
            last_message = updates['result'][-1]['message']
            
            if 'photo' in last_message and str(last_message['chat']['id']) == TELEGRAM_CHAT_ID:
                file_id = last_message['photo'][-1]['file_id']
                
                file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info['result']['file_path']}"
                break
        
    if not file_url:
        print("Taymaut: ne polucheno izobrazheniye ot bota.")
        return "Timeout Error", 504

    # 3. SKACHIVANIYE I OBRABOTKA (JPEG -> RGB565)
    try:
        image_response = requests.get(file_url)
        img = Image.open(io.BytesIO(image_response.content))

        # Izmeneniye razmera dlya ST7735 128x160
        img = img.resize((128, 160))
        
        data = io.BytesIO()
        
        for pixel in img.convert("RGB").getdata():
            r = (pixel[0] >> 3) & 0x1F  
            g = (pixel[1] >> 2) & 0x3F  
            b = (pixel[2] >> 3) & 0x1F  
            color = (r << 11) | (g << 5) | b
            data.write(struct.pack('<H', color))

        data.seek(0)
        
        # 4. OT-PRAVKA SYRYKH DANNYKH (RGB565) NA ESP32
        print("Ot-pravka 40960 bayt na ESP32...")
        return send_file(
            data,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='image_data'
        )
    except Exception as e:
        print(f"Oshibka obrabotki izobrazheniya: {e}")
        return "Image Processing Error", 500

# !!! OBRATITE Vnimaniye: zdes' net app.run(). Ego zapustit Gunicorn.
