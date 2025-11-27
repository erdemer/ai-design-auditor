# config.py
import os
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# API Anahtarını al
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("HATA: GOOGLE_API_KEY bulunamadı.")
    print("Lütfen proje klasörünüze bir .env dosyası oluşturup içine 'GOOGLE_API_KEY=...' ekleyin.")
    exit()

# Karşılaştırma için tolerans
DEFAULT_TOLERANCE_PX = 18
DIMENSION_TOLERANCE_PERCENT = 0.15

# Uygulama tarafının hangi analiz modu ile okunacağını belirler:
# - 'xml': UIAutomator XML'den okunur (mevcut davranış, sadece layout + metin).
# - 'ai':  App ekran görüntüsü de Gemini ile analiz edilir (stil + layout).
APP_ANALYSIS_MODE = os.getenv("APP_ANALYSIS_MODE", "ai").lower()