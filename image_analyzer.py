# image_analyzer.py
import google.generativeai as genai
import config
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import json
import re
import os
import math

# Yapılandırma ve Model Hazırlığı
try:
    genai.configure(api_key=config.GOOGLE_API_KEY)
    # Görsel analiz için en iyi model
    # Temperature 0.0 for deterministic output
    vision_model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"temperature": 0.0}
    )
except Exception as e:
    print(f"[AI] Model yüklenirken hata oluştu: {e}")
    vision_model = None

# Uzun ekran görüntülerini bölmek için dilim yüksekliği
SLICE_HEIGHT = 1920

# --- GÜNCELLENMİŞ SİSTEM TALİMATI (V4) ---
SYSTEM_PROMPT = """
Sen uzman bir UI Test Otomasyon mühendisisin. Görevin bu mobil uygulama ekran görüntüsündeki GÖRSEL NESNELERİ tespit etmektir.
Yorum yapma, sadece gördüğün somut nesneleri işaretle.

1. TESPİT KURALLARI:
   - "Text": Tüm görünür metinler, etiketler, başlıklar, telefon numaraları.
   - "Button": Tıklanabilir olduğu belli olan, çerçeveli veya renkli dolgulu alanlar.
   - "Icon": Geri oku, çarpı, tik, menü ikonları gibi simgeler.
   - "Input": Metin girilebilen alanlar (Genelde gri çizgili veya kutulu).
   - "Image": Kullanıcı avatarları, ürün resimleri vb.

2. İSİMLENDİRME KURALLARI (ÇOK ÖNEMLİ):
   - "name" alanına, bileşenin üzerindeki metni veya işlevini yaz.
   - Örnek: "giris_yap_butonu", "kullanici_adi_label", "geri_don_ikonu".
   - ASLA "text_1", "button_2" gibi anlamsız, jenerik isimler verme.

3. YASAKLAR VE FİLTRELER:
   - "Container", "View", "Group" gibi kapsayıcıları ASLA alma. Sadece en uç (leaf) elemanları al.
   - İçinde metin veya ikon olmayan BOŞ ALANLARI, arka planları ASLA işaretleme.
   - Hata mesajlarını (kırmızı uyarı yazıları) "Button" veya "Input" sanma; onlar "Text"tir.

JSON ÇIKTI FORMATI:
[
  {
    "name": "kaydet_butonu",
    "type": "Button",
    "bounds": { "x": 0, "y": 0, "w": 100, "h": 50 },
    "text_content": "Kaydet", 
    "estimated_color": "#FFFFFF",
    "estimated_fontSize_dp": 16,
    "estimated_backgroundColor": "#E30613"
  }
]
Sadece saf JSON döndür. Markdown (```json) kullanma.
"""

# --- CONTEXT AWARE PROMPT (Hybrid Mode) ---
CONTEXT_AWARE_PROMPT_TEMPLATE = """
Sen uzman bir UI Test Otomasyon mühendisisin. Görevin, sana verilen "BEKLENEN BİLEŞENLER LİSTESİ"ni (Figma'dan gelen veriler) kullanarak, bu mobil uygulama ekran görüntüsündeki karşılıklarını doğrulamak ve tespit etmektir.

GİRDİ:
1. Ekran Görüntüsü (Görsel)
2. Beklenen Bileşenler Listesi (Aşağıda)

BEKLENEN BİLEŞENLER:
{component_list_str}

GÖREVİN:
1. Listedeki her bir bileşeni görselde ara.
2. Eğer görselde varsa, görseldeki GERÇEK KONUMUNU (bounds) ve TİPİNİ işaretle.
3. Eğer listede olmayan ama görselde belirgin olan başka önemli bileşenler varsa, onları da ekle.
4. İsimlendirmede, eğer eşleşme bulursan listedeki "name"i kullanmaya çalış.

JSON ÇIKTI FORMATI (Aynı):
[
  {{
    "name": "kaydet_butonu",
    "type": "Button",
    "bounds": {{ "x": 0, "y": 0, "w": 100, "h": 50 }},
    "text_content": "Kaydet", 
    "estimated_color": "#FFFFFF"
  }}
]
Sadece saf JSON döndür.
"""



def _extract_json_from_response(text: str):
    """AI yanıtından saf JSON'ı ayıklar."""
    if not text: return None
    # Markdown temizliği
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"```(.*?)```", text, re.DOTALL)
    if match: return match.group(1).strip()

    # Köşeli parantez bul ve ayıkla
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start: end + 1].strip()
    return text.strip()


def _save_debug_image(original_image_path, json_data):
    """
    Analiz sonucunu görselleştirir.
    Kutuların üzerine Tip ve İsim yazar.
    """
    try:
        img = PIL.Image.open(original_image_path).convert("RGB")
        draw = PIL.ImageDraw.Draw(img)

        # Renk Paleti
        colors = {
            "Text": "blue",
            "Button": "#00FF00",  # Parlak Yeşil
            "Icon": "magenta",
            "Input": "orange",
            "Image": "cyan",
            "Container": "red"  # Olmaması gerekenler kırmızı
        }

        for comp in json_data:
            b = comp.get("bounds")
            ctype = comp.get("type", "Container")
            cname = comp.get("name", "unknown")
            color = colors.get(ctype, "red")

            if b:
                x, y, w, h = b['x'], b['y'], b['w'], b['h']

                # 1. Kutuyu Çiz
                draw.rectangle([x, y, x + w, y + h], outline=color, width=3)

                # 2. Etiket Yaz (Arka planlı)
                # Metin: "Type: Name"
                label = f"{ctype}: {cname}"

                # Metin boyutunu kabaca hesapla (Font yüklemeyle uğraşmadan)
                text_w = len(label) * 7
                text_h = 14

                # Etiket kutusunun konumu (Kutunun hemen üstü veya içi)
                # Eğer kutu çok yukarıdaysa içine yaz, değilse üstüne yaz.
                label_y = y - 16 if y > 16 else y

                # Etiket arka planı
                draw.rectangle([x, label_y, x + text_w, label_y + text_h], fill=color)

                # Etiket yazısı (Beyaz)
                draw.text((x + 2, label_y), label, fill="white")

        base_name = os.path.basename(original_image_path)
        debug_filename = f"DEBUG_AI_VISION_{base_name}"
        img.save(debug_filename)
        print(f"[DEBUG] Görsel kaydedildi: {debug_filename}")

    except Exception as e:
        print(f"[DEBUG] Resim çizme hatası: {e}")


def _analyze_single_slice(pil_image, offset_y, part_no, expected_components=None):
    """Tek bir görüntü dilimini analiz eder."""
    try:
        print(f"   -> [AI] Parça {part_no} analiz ediliyor (Offset: {offset_y})...")
        
        prompt_to_use = SYSTEM_PROMPT
        if expected_components:
            # Format expected components for this slice (simple heuristic: include all or filter by y)
            # For simplicity, we pass a summary of all components to give context
            # Or better: filter components that are likely in this slice range?
            # Let's pass a simplified list of names/types/texts to avoid token limit issues
            
            comp_strs = []
            for c in expected_components:
                # Optional: Filter by Y coordinate if we trust Figma Y enough
                # if c['bounds']['y'] ...
                
                c_name = c.get('name', 'Unknown')
                c_type = c.get('type', 'Unknown')
                c_text = c.get('text_content', '')
                comp_strs.append(f"- [{c_type}] '{c_name}' (Text: '{c_text}')")
            
            # Limit to top 50 to avoid context window issues if list is huge
            if len(comp_strs) > 50:
                comp_strs = comp_strs[:50] + ["... ve diğerleri"]
                
            component_list_str = "\n".join(comp_strs)
            prompt_to_use = CONTEXT_AWARE_PROMPT_TEMPLATE.format(component_list_str=component_list_str)
            print(f"   -> [AI] Hybrid Mode: {len(comp_strs)} beklenen bileşen ile prompt oluşturuldu.")

        response = vision_model.generate_content([prompt_to_use, pil_image])

        raw_text = getattr(response, "text", str(response))
        json_str = _extract_json_from_response(raw_text)

        if not json_str:
            print(f"   -> [UYARI] Parça {part_no} boş veri döndü.")
            return []

        data = json.loads(json_str)
        if not isinstance(data, list): return []

        valid_data = []
        for comp in data:
            if "bounds" in comp:
                # Koordinatları global konuma oturt
                comp["bounds"]["y"] += offset_y

                # --- PYTHON TARAFI FİLTRELEME ---
                # AI bazen prompta uymaz, burada ikinci bir güvenlik kontrolü yapıyoruz.
                c_type = comp.get("type", "")
                c_text = comp.get("text_content", "")

                # Eğer tipi Container ise ve metin yoksa -> ÇÖP (Hayalet Kutu)
                if c_type == "Container" and not c_text:
                    continue

                    # Eğer sınırları (bounds) 0 veya negatifse -> ÇÖP
                if comp["bounds"]["w"] <= 0 or comp["bounds"]["h"] <= 0:
                    continue

                valid_data.append(comp)

        return valid_data
    except Exception as e:
        print(f"   -> [HATA] Parça {part_no} analiz hatası: {e}")
        return []


def analyze_image(image_path: str, expected_components=None):
    """Ana analiz fonksiyonu. expected_components (Figma Data) varsa Hybrid modda çalışır."""
    if not vision_model:
        print("[AI] Model yüklü değil.")
        return None

    try:
        full_img = PIL.Image.open(image_path)
        width, total_height = full_img.size

        final_json = []

        # Resim kısaysa tek seferde işle
        if total_height <= SLICE_HEIGHT:
            print("[AI] Tek parça analiz ediliyor...")
            final_json = _analyze_single_slice(full_img, 0, 1, expected_components)
        else:
            # Resim uzunsa parçala
            num_slices = math.ceil(total_height / SLICE_HEIGHT)
            print(f"[AI] Resim {total_height}px yüksekliğinde, {num_slices} parçaya bölünüyor...")

            for i in range(num_slices):
                top = i * SLICE_HEIGHT
                # Son parça değilse, overlap ekle (örn: 100px) ki kesilen bileşenler kaybolmasın
                # Ancak bu duplicate yaratabilir, şimdilik basit tutalım.
                # Deterministic olması için overlap'i şimdilik kapalı tutuyoruz, ama 
                # temperature 0 ile zaten daha stabil olacak.
                bottom = min(top + SLICE_HEIGHT, total_height)

                # Son parça çok küçükse atla (Gürültü ve yarım bileşen riski)
                if (bottom - top) < 50 and i > 0:
                    continue

                slice_img = full_img.crop((0, top, width, bottom))
                slice_data = _analyze_single_slice(slice_img, top, i + 1, expected_components)
                final_json.extend(slice_data)

        print(f"[AI] Analiz bitti. Toplam {len(final_json)} bileşen bulundu.")

        # Debug görselini kaydet
        _save_debug_image(image_path, final_json)

        return final_json

        return final_json

    except Exception as e:
        # Check for ResourceExhausted (Quota Limit)
        # Since we might not have the exact class imported, check string
        error_str = str(e)
        if "429" in error_str or "ResourceExhausted" in error_str or "Quota exceeded" in error_str:
            raise Exception("Gemini AI Quota Exceeded. Please wait a minute or check your billing.")
        elif "403" in error_str:
            raise Exception("Gemini API Permission Denied. Check your API Key.")
        else:
            raise Exception(f"AI Analysis Error: {error_str}")


def detect_system_bars(image_path: str):
    """
    Görüntüdeki Status Bar ve Navigation Bar yüksekliklerini AI ile tespit eder.
    """
    if not vision_model:
        return {"status_bar_height": 0, "nav_bar_height": 0}

    prompt = """
    Analyze this mobile UI screenshot.
    Detect the height (in pixels) of the system Status Bar (at the very top) and the system Navigation Bar/Home Indicator (at the very bottom).
    
    Return ONLY a JSON object with these keys:
    {
      "status_bar_height": int,
      "nav_bar_height": int
    }
    
    If a bar is not present or clearly visible, set its value to 0.
    Do not include any markdown formatting, just the raw JSON.
    """

    try:
        img = PIL.Image.open(image_path)
        response = vision_model.generate_content([prompt, img])
        
        raw_text = getattr(response, "text", str(response))
        json_str = _extract_json_from_response(raw_text)
        
        if json_str:
            data = json.loads(json_str)
            return {
                "status_bar_height": int(data.get("status_bar_height", 0)),
                "nav_bar_height": int(data.get("nav_bar_height", 0))
            }
    except Exception as e:
        print(f"[AI] Bar tespiti hatası: {e}")
    
    return {"status_bar_height": 0, "nav_bar_height": 0}