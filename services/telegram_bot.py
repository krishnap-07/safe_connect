import os
import requests
from google import genai
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
            area = address.get("suburb") or address.get("neighbourhood") or address.get(
                "city") or address.get("town") or address.get("county")
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

    client = genai.Client(api_key=gemini_key)

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return None


def send_telegram_alert(
    lat: float,
    lon: float,
    description: str,
    disaster_type: str = "Unknown",
    priority: str = "MEDIUM",
    priority_score: int = 0,
    human_detected: bool = False,
    human_count: int = 0,
    damage_level: str = "Unknown",
    water_depth: str = "N/A",
    hospital_name: str = "UNASSIGNED",
    image_path: str = None,
) -> bool:
    """Generates a detailed alert with image and sends it to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID_HERE":
        print("Telegram Bot Token or Chat ID not configured. Skipping broadcast.")
        return False

    # Build a rich, descriptive caption
    area_name = get_area_name(lat, lon)

    # Severity emoji mapping
    sev_emoji = {"HIGH": "🔴", "CRITICAL": "🔴",
                 "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
    human_text = f"✅ YES — {human_count} person(s) detected" if human_detected else "❌ No humans detected"

    caption_lines = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🚨 *SAFE CONNECT — DISASTER ALERT* 🚨",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📍 *Location:* {area_name}",
        f"🌐 *GPS:* `{lat:.6f}, {lon:.6f}`",
        "",
        f"🔥 *Disaster Type:* {disaster_type}",
        f"📝 *Description:* {description}",
        "",
        f"{sev_emoji} *Priority:* {priority} ({priority_score}%)",
        f"👤 *Human Life:* {human_text}",
        f"🏚 *Damage Level:* {damage_level}",
    ]

    if water_depth and water_depth not in ("N/A", "Unknown"):
        caption_lines.append(f"🌊 *Water Depth:* {water_depth}")

    caption_lines.extend([
        "",
        f"🏥 *Nearest Hospital:* {hospital_name}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "⚡ *AI-powered alert by SAFE CONNECT*",
    ])

    caption = "\n".join(caption_lines)

    # Also generate the Gemini tri-lingual alert
    gemini_text = generate_alert_text(lat, lon, description)

    success = False

    # 1. Send the image with the detailed caption
    if image_path:
        upload_dir = os.path.join(os.path.dirname(
            os.path.dirname(__file__)), "uploads")
        full_image_path = os.path.join(upload_dir, image_path)

        if os.path.exists(full_image_path):
            try:
                photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                with open(full_image_path, "rb") as photo:
                    photo_payload = {
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "Markdown",
                    }
                    files = {"photo": photo}
                    resp = requests.post(
                        photo_url, data=photo_payload, files=files, timeout=15)
                    resp.raise_for_status()
                    success = True
                    print(f"Telegram photo alert sent successfully.")
            except Exception as e:
                print(
                    f"Telegram photo send failed: {e}. Falling back to text-only.")

    # 2. If photo failed or no image, send as text message
    if not success:
        try:
            text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": caption,
                "parse_mode": "Markdown",
            }
            resp = requests.post(text_url, json=payload, timeout=10)
            resp.raise_for_status()
            success = True
        except Exception as e:
            print(f"Telegram text alert failed: {e}")

    # 3. Send the Gemini tri-lingual translation as a follow-up message
    if gemini_text and success:
        try:
            text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": gemini_text,
                "parse_mode": "Markdown",
            }
            requests.post(text_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram translation follow-up failed: {e}")

    return success


def send_final_report_telegram(incident: dict, rescued_count: int, dead_count: int, hospital_name: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not bot_token or not chat_id or not gemini_key:
        return False

    area_name = get_area_name(
        float(incident['latitude']), float(incident['longitude']))

    client = genai.Client(api_key=gemini_key)

    prompt = f"""
    You are an emergency response official issuing a final summary report for a resolved disaster.
    Location: {area_name}
    Disaster Type: {incident['disaster_type']}
    Description: {incident['description']}
    Total Rescued/Admitted: {rescued_count}
    Total Casualties (Dead): {dead_count}
    Handling Hospital: {hospital_name}
    
    Generate a formal, respectful, and brief news-style final report (max 3 sentences per language).
    Format exactly like this:
    
    ✅ **FINAL INCIDENT REPORT** ✅
    [English version here]
    
    ✅ **अंतिम घटना अहवाल** ✅
    [Marathi version here]
    
    ✅ **अंतिम घटना रिपोर्ट** ✅
    [Hindi version here]
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        gemini_text = response.text.strip()
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return False

    try:
        text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": gemini_text,
        }
        requests.post(text_url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram text alert failed: {e}")
        return False
