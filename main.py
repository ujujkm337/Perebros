import requests
import io
import time
import struct
from PIL import Image
from flask import jsonify # Nuzhno dlya vernoy otpravki soobshcheniy ob oshibkakh

# --- !!! VAZHNO: VSTAV'TE SVOI ZNACHENIYA SYUDA !!! ---
# Vash TOKEN iz BotFather
TELEGRAM_BOT_TOKEN = "ВСТАВЬТЕ_ВАШ_ТОКЕН_BOTFATHERA"    
# Vash CHAT_ID, kotoryy vy uspeshno poluchili
TELEGRAM_CHAT_ID = "ВСТАВЬТЕ_ВАШ_CHAT_ID"               
# Promt, kotoryy budet ot-pravlyat'sya pri kazhdom nazhatii knopki
PROMPT = "сгенерируй кошку в реалистичном стиле, 128x160" 
# --- !!! VAZHNO: VSTAV'TE SVOI ZNACHENIYA SYUDA !!! ---

def giga_chat_proxy(request):
    """Glavnaya funktsiya, kotoruyu vyzovet ESP32 po HTTP-zaprosu."""
    
    print(f"[{time.strftime('%H:%M:%S')}] Poluchen zapros ot ESP32.")

    # 1. OT-PRAVKA KOMANDY GigaChat'u
    try:
        # Ot-pravlyayem soobshcheniye v VASH proksi-chat, chtoby GigaChat nachal generatsiyu
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': PROMPT}
        )
    except Exception as e:
        # V sluchaye oshibki vozvrashchayem tekst dlya obrabotki ESP32
        return jsonify({'error': f"Error sending to Telegram: {e}"}), 500

    # 2. OZHIDANIYE I POLUCHENIYE IZOBRAZHENIYA
    file_url = None
    start_time = time.time()
    
    # Zhdem do 75 sekund, poka GigaChat otvetit
    while not file_url and (time.time() - start_time < 75): 
        time.sleep(3) # Zhdem 3 sekundy pered novym oprosom
        
        # Opros Telegram API (zagruzka poslednikh soobshcheniy iz chata)
        updates = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-1").json()
        
        if updates['ok'] and updates['result']:
            last_message = updates['result'][-1]['message']
            
            # Proveryayem, poluchili li my foto v nashem chatID
            if 'photo' in last_message and str(last_message['chat']['id']) == TELEGRAM_CHAT_ID:
                # Poluchayem ID samogo bol'shogo fayla v soobshchenii
                file_id = last_message['photo'][-1]['file_id']
                
                # Poluchayem pryamuyu ssylku na skachivaniye JPEG
                file_info = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info['result']['file_path']}"
                print(f"[{time.strftime('%H:%M:%S')}] Poluchena ssylka na izobrazheniye.")
                break
        
    if not file_url:
        print(f"[{time.strftime('%H:%M:%S')}] Taymaut polucheniya izobrazheniya.")
        return jsonify({'error': "Timeout: No image received from GigaChat bot"}), 504

    # 3. SKACHIVANIYE I OBRABOTKA (JPEG -> RGB565)
    try:
        # Skachivayem JPEG-fayl
        image_response = requests.get(file_url)
        img = Image.open(io.BytesIO(image_response.content))

        # Izmenyayem razmer (vazhno dlya ST7735)
        img = img.resize((128, 160))
        
        data = io.BytesIO()
        
        # Konvertatsiya v format RGB565 (trebuyemyy format dlya displeya)
        for pixel in img.convert("RGB").getdata():
            r = (pixel[0] >> 3) & 0x1F  # 5 bit
            g = (pixel[1] >> 2) & 0x3F  # 6 bit
            b = (pixel[2] >> 3) & 0x1F  # 5 bit
            color = (r << 11) | (g << 5) | b
            
            # Zapis' baytov v formate Little Endian (Vazhno!)
            data.write(struct.pack('<H', color))

        data.seek(0)
        
        print(f"[{time.strftime('%H:%M:%S')}] Konvertatsiya zavershena, ot-pravka na ESP32.")
        
        # 4. OT-PRAVKA SYRYKH BAYTOV NA ESP32
        # My ot-pravlyayem 40960 bayt chistogo izobrazheniya
        return data.read(), 200, {'Content-Type': 'application/octet-stream'}
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Oshibka obrabotki: {e}")
        return jsonify({'error': f"Image Processing Error: {e}"}), 500