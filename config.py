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
    # İsterseniz burada programı durdurabilirsiniz
    # exit()

# Karşılaştırma için tolerans
DEFAULT_TOLERANCE_PX = 10