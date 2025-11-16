# image_analyzer.py
import google.generativeai as genai
import config
import PIL.Image
import json
import re

# Gemini API'yi yapılandır
try:
    genai.configure(api_key=config.GOOGLE_API_KEY)
    vision_model = genai.GenerativeModel('gemini-2.5-pro')
except Exception as e:
    print(f"[AI] Gemini modeli yüklenirken hata oluştu: {e}")
    vision_model = None

# --- YENİ V6 PROMPT: AI-DESTEKLİ EŞLEŞTİRME ---
SYSTEM_PROMPT = """
Sen, bir UI/UX tasarımını piksel hassasiyetinde analiz eden bir uzmansın.
Görevin, sana verilen iki resmi (Resim 1: Figma Tasarımı, Resim 2: App SS) karşılaştırmaktır.

Temel hedefin, Resim 1'deki her bileşeni bulmak ve Resim 2'de buna karşılık gelen (eşleşen)
bileşeni bulmaktır.

Sonucu, SADECE eşleşen çiftleri içeren bir JSON listesi olarak döndür.
Bir bileşenin eşleşeni yoksa, onu listeye EKLEME.
Başka HİÇBİR açıklama metni ekleme. Sadece JSON listesini tek bir kod bloğu (```json ... ```) içinde ver.

KURALLAR (ÇOK ÖNEMLİ):
1.  EŞLEŞTİRME: Eşleştirmeyi bileşenin TİPİ (Text, Image, Icon, Container) ve GEOMETRİK KONUMUNA (örn: sol üstteki resim, ikinci başlık) göre yap.
2.  İSİMLENDİRME: 'name' için JENERİK ve YAPISAL isimler kullan (örn: 'driver_image', 'stat_card_1', 'section_title_1').
3.  HASSASİYET: 'bounds' kutuları, bileşenin GÖRÜNÜR piksellerine 'SIFIR PADDING' (zero-padding) ile SIKIŞIK (tight) olmalıdır.
4.  GÜRÜLTÜ ENGELLEME: Sistem bileşenlerini (Status Bar, Navigation Bar) ve içindeki ikonları (pil, saat, wifi ikonu) TAMAMEN GÖRMEZDEN GEL. Onları JSON listesine EKLEME.

JSON ÇIKTI FORMATI (SADECE BU FORMATTA BİR LİSTE DÖNDÜR):
[
  {
    "name": "jenerik_ve_sirali_snake_case_isim",
    "figma_analysis": {
      "type": "Text | Image | Icon | Container",
      "bounds": { "x": 0, "y": 0, "w": 0, "h": 0 },
      "text_content": "Eğer 'Text' tipindeyse içindeki metin, değilse null",
      "estimated_color": "Eğer 'Text' veya 'Icon' ise TAHMINI hex renk kodu, değilse null",
      "estimated_fontSize_dp": "Eğer 'Text' ise TAHMINI yazı tipi boyutu (sadece sayı, dp olarak), değilse null",
      "estimated_backgroundColor": "Eğer 'Container' veya 'Button' ise TAHMINI hex arka plan rengi, değilse null"
    },
    "app_analysis": {
      "type": "Text | Image | Icon | Container",
      "bounds": { "x": 0, "y": 0, "w": 0, "h": 0 },
      "text_content": "Eğer 'Text' tipindeyse içindeki metin, değilse null",
      "estimated_color": "Eğer 'Text' veya 'Icon' ise TAHMINI hex renk kodu, değilse null",
      "estimated_fontSize_dp": "Eğer 'Text' ise TAHMINI yazı tipi boyutu (sadece sayı, dp olarak), değilse null",
      "estimated_backgroundColor": "Eğer 'Container' veya 'Button' ise TAHMINI hex arka plan rengi, değilse null"
    }
  }
]
"""


def _clean_json_response(raw_response):
    """AI'nin döndürdüğü '```json ... ```' gibi metinleri temizler."""
    match = re.search(r'```json\s*([\s\S]+?)\s*```', raw_response)
    if match:
        return match.group(1)
    return raw_response.strip()


def analyze_image_pair(figma_image_path: str, app_image_path: str):
    """
    İki görüntüyü (Figma ve App) Vision AI kullanarak karşılaştırır ve
    eşleşen bileşen çiftlerinin JSON listesini döndürür.
    """
    if not vision_model:
        print("[AI] HATA: Vision modeli yüklenemedi. config.py dosyasını kontrol edin.")
        return None

    print(f"[AI] Eşleştirme Analizi Başlatıldı...")
    print(f"   Figma: '{figma_image_path}'")
    print(f"   App:   '{app_image_path}'")
    print(f"   (Bu işlem 30-60 saniye sürebilir, Pro modeli kullanılıyor...)")

    try:
        figma_img = PIL.Image.open(figma_image_path)
        app_img = PIL.Image.open(app_image_path)

        response = vision_model.generate_content([
            SYSTEM_PROMPT,
            "Resim 1 (Figma Tasarımı):",
            figma_img,
            "Resim 2 (App Ekran Görüntüsü):",
            app_img
        ])

        cleaned_json_str = _clean_json_response(response.text)

        json_data = json.loads(cleaned_json_str)

        print(f"[AI] Analiz tamamlandı. {len(json_data)} adet EŞLEŞEN bileşen çifti bulundu.")
        return json_data

    except PIL.UnidentifiedImageError:
        print(f"[AI] HATA: Geçerli bir resim dosyası bulunamadı.")
        return None
    except json.JSONDecodeError:
        print(f"[AI] HATA: AI'den gelen yanıt JSON formatında değil.")
        print(f"   Gelen Ham Veri: {response.text[:200]}...")
        return None
    except Exception as e:
        print(f"[AI] HATA: Görüntü analizi sırasında beklenmedik bir hata oluştu: {e}")
        return None