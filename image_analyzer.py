# image_analyzer.py
import google.generativeai as genai
import config
import PIL.Image
import json
import re

try:
    genai.configure(api_key=config.GOOGLE_API_KEY)
    vision_model = genai.GenerativeModel("gemini-2.5-pro")
except Exception as e:
    print(f"[AI] Gemini modeli yüklenirken hata oluştu: {e}")
    vision_model = None


SYSTEM_PROMPT = """
Sen, bir UI/UX tasarımını piksel hassasiyetinde analiz eden bir uzmansın.
Görevin, sana verilen TEK bir görüntüdeki TÜM görünür UI bileşenlerini (Text, Image, Button, Icon, Container/Card) tespit etmektir.
HASSASİYET çok önemlidir. Bu bir kedi/köpek resmi değil, bu bir UI layout'u.

Sonucu, bir JSON listesi olarak döndür. Başka HİÇBİR açıklama metni ekleme.
Sadece JSON listesini tek bir kod bloğu (```json ... ```) içinde ver.

KURALLAR:
1. 'bounds' kutuları, bileşenin GÖRÜNÜR piksellerine sıkı (tight) olmalı.
2. Status bar, navigation bar, sistem ikonları (saat, wifi, pil, back gesture bar) JSON'a eklenmeyecek.
3. 'name' için jenerik, yapısal isimler kullan (örn: 'header_title', 'profile_avatar', 'primary_button').

JSON YAPISI (her bileşen için):
{
  "name": "jenerik_ve_sirali_snake_case_isim",
  "type": "Text | Image | Icon | Container",
  "bounds": { "x": 0, "y": 0, "w": 0, "h": 0 },
  "text_content": "Eğer 'Text' tipindeyse metin, değilse null",
  "estimated_color": "Eğer 'Text' veya 'Icon' ise TAHMINI hex renk, değilse null",
  "estimated_fontSize_dp": "Eğer 'Text' ise TAHMINI font boyutu (sadece sayı, dp), değilse null",
  "estimated_backgroundColor": "Eğer 'Container' veya 'Button' ise TAHMINI hex arka plan rengi, değilse null"
}
"""


def _extract_json_from_response(text: str):
    """
    Gemini cevabından ```json ... ``` bloğunu söküp çıkarır.
    - Önce ```json ... ``` arar
    - Bulamazsa ``` ... ``` arar
    - En sonda da [ ile başlayan JSON'u çıkarmayı dener
    """
    if not text:
        return None

    # 1) ```json ... ``` bloğu (DOĞRUSU: \s, tek backslash!)
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 2) Sıradan ``` ... ``` bloğu
    match = re.search(r"```(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 3) Son çare: ilk '[' ile son ']' arasını al
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    # Hiçbiri tutmadıysa, komple metni döndür
    return text.strip()


def analyze_image(image_path: str):
    """
    Verilen görüntüyü (Figma SS veya App SS) Gemini ile analiz eder ve
    JSON listesi döndürür. Hata olursa None döner.
    """
    if not vision_model:
        print("[AI] Uyarı: Gemini modeli yüklü değil, analiz yapılamıyor.")
        return None

    try:
        image = PIL.Image.open(image_path)
    except FileNotFoundError:
        print(f"[AI] HATA: Görüntü dosyası bulunamadı: {image_path}")
        return None
    except Exception as e:
        print(f"[AI] HATA: Görüntü açılırken hata: {e}")
        return None

    try:
        print(f"[AI] '{image_path}' için UI bileşen analizi isteniyor...")
        response = vision_model.generate_content(
            [
                SYSTEM_PROMPT,
                image,
            ]
        )

        raw_text = getattr(response, "text", str(response))
        cleaned_json_str = _extract_json_from_response(raw_text)

        if not cleaned_json_str:
            print("[AI] HATA: Yanıttan JSON çıkarılamadı (boş).")
            return None

        try:
            json_data = json.loads(cleaned_json_str)
        except json.JSONDecodeError as e:
            print("[AI] HATA: AI'den gelen yanıt JSON formatında değil.")
            print(f"   JSONDecodeError: {e}")
            print(f"   Gelen Ham Veri (ilk 300): {raw_text[:300]!r}")
            return None

        if not isinstance(json_data, list):
            print("[AI] Uyarı: JSON liste değil, yine de döndürüyorum.")
        else:
            print(f"[AI] Analiz tamamlandı. {len(json_data)} adet bileşen bulundu.")

        return json_data

    except PIL.UnidentifiedImageError:
        print(f"[AI] HATA: '{image_path}' geçerli bir resim dosyası değil.")
        return None
    except Exception as e:
        print(f"[AI] HATA: Görüntü analizi sırasında beklenmedik bir hata oluştu: {e}")
        return None