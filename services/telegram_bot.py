import os
import requests
import google.generativeai as genai
from typing import Optional

def get_area_name(lat: float, lon: float) -> str:
    """Reverse geocodes coordinates using OpenStreetMap's free Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        headers = {"User-Agent": "SAFER_CONNECT_APP"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Try to get the most relevant local area name
            address = data.get("address", {})
            area = address.get("suburb") or address.get("neighbourhood") or address.get("city") or address.get("town") or address.get("county")
            if area:
                return area
    except Exception as e:
        print(f"Geocoding error: {e}")
    return f"{lat:.4f}, {lon:.4f}"

def generate_alert_text(lat: float, lon: float, description: str) -> Optional[str]:
    """Uses Gemini to generate a tri-lingual news alert."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "YOUR_GEMINI_API_KEY_HERE":
        print("Gemini API key not configured. Skipping translation.")
        return None

    area_name = get_area_name(lat, lon)
    
    genai.configure(api_key=gemini_key)
    
    # Use gemini-1.5-flash as it's fast and standard for this
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an emergency broadcasting system. 
    A disaster has just been reported.
    Area/Location: {area_name} (Coordinates: {lat}, {lon})
    Report Description: {description}
    
    Generate a short, urgent, news-like alert (max 3 sentences per language) to be posted on a Telegram channel.
    Format the output exactly like this, separating the languages with blank lines:
    
    🚨 **EMERGENCY ALERT** 🚨
    [English version here]
    
    🚨 **आपात्कालीन सूचना** 🚨
    [Hindi version here]
    
    🚨 **आणीबाणीचा इशारा** 🚨
    [Marathi version here]
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return None

def send_telegram_alert(lat: float, lon: float, description: str) -> bool:
    """Generates the alert and sends it to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID_HERE":
        print("Telegram Bot Token or Chat ID not configured. Skipping broadcast.")
        return False
        
    message = generate_alert_text(lat, lon, description)
    if not message:
        # Fallback if Gemini fails or isn't configured
        area_name = get_area_name(lat, lon)
        message = f"🚨 **EMERGENCY ALERT** 🚨\nDisaster reported near {area_name}.\nDescription: {description}"
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram API error: {e}")
        return False
