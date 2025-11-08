# adb_client.py
import subprocess
import os
import time
import re

# Cihazdaki geçici dosya yolu
DEVICE_TEMP_PATH = "/sdcard/ai_audit_screenshot.png"


def _get_screen_dimensions():
    """
    Cihazın fiziksel ekran boyutlarını 'adb shell wm size' ile alır.
    (width, height) döndürür, başarısız olursa (None, None) döndürür.
    """
    try:
        result = subprocess.run(
            ["adb", "shell", "wm", "size"],
            check=True, capture_output=True, text=True, timeout=5
        )
        match = re.search(r'Physical size:\s*(\d+)x(\d+)', result.stdout)
        if match:
            width = int(match.group(1))
            height = int(match.group(2))
            print(f"[ADB] Cihaz boyutu algılandı: {width}x{height}")
            return width, height
        else:
            print(f"[ADB] HATA: 'wm size' çıktısı anlaşılamadı. Çıktı: {result.stdout}")
            return None, None
    except Exception as e:
        print(f"[ADB] HATA: Cihaz boyutu alınamadı: {e}")
        return None, None


def take_screenshot(part_index):
    """
    Bağlı ADB cihazından ekran görüntüsü alır ve 'app_screenshot_part_1.png' gibi
    numaralandırılmış bir isimle kaydeder.
    """
    output_filename = f"app_screenshot_part_{part_index}.png"
    print(f"[ADB] Cihazdan ekran görüntüsü (Parça {part_index}) alınıyor...")

    try:
        # 1. Cihazda ekran görüntüsü al
        subprocess.run(
            ["adb", "shell", "screencap", "-p", DEVICE_TEMP_PATH],
            check=True, capture_output=True, timeout=10
        )

        # 2. Ekran görüntüsünü bilgisayara çek
        if os.path.exists(output_filename):
            os.remove(output_filename)

        subprocess.run(
            ["adb", "pull", DEVICE_TEMP_PATH, output_filename],
            check=True, capture_output=True, timeout=10
        )

        # 3. Cihazdaki geçici dosyayı sil
        subprocess.run(
            ["adb", "shell", "rm", DEVICE_TEMP_PATH],
            capture_output=True, timeout=5
        )

        print(f"[ADB] Ekran görüntüsü başarıyla '{output_filename}' olarak kaydedildi.")
        return output_filename

    except Exception as e:
        print(f"[ADB] HATA: ADB komutu başarısız oldu: {e}")
        return None


def scroll_down(crop_top_px=0, crop_bottom_px=0):
    """
    Cihazda dikey bir kaydırma (swipe) hareketi yapar.
    (GÜNCELLENDİ: Artık kırpılmış alanın %80'i kadar kaydırır)
    """
    print("[ADB] Ekranda aşağı kaydırılıyor (swipe)...")

    # 1. Cihaz boyutlarını al
    width, height = _get_screen_dimensions()
    if not width or not height:
        print("[ADB] HATA: Cihaz boyutu alınamadığı için kaydırma yapılamıyor.")
        return False

    # 2. Orantılı koordinatları hesapla
    scrollable_top = crop_top_px
    scrollable_bottom = height - crop_bottom_px
    scrollable_height = scrollable_bottom - scrollable_top

    if scrollable_height <= 0:
        print("[ADB] HATA: Kırpma ayarları tüm ekranı kaplıyor, kaydırma yapılamaz.")
        return False

    # 3. Güvenli Kaydırma Miktarı
    scroll_amount = int(scrollable_height * 0.8)

    x_coord = int(width / 2)
    y_start = scrollable_top + int(scrollable_height * 0.8)
    y_end = y_start - scroll_amount

    if y_end < scrollable_top:
        y_end = scrollable_top

    duration_ms = 400

    print(f"[ADB] Güvenli Kaydırma Komutu: swipe {x_coord} {y_start} {x_coord} {y_end} {duration_ms}")

    try:
        # 4. ADB komutunu çalıştır
        subprocess.run(
            ["adb", "shell", "input", "swipe",
             str(x_coord), str(y_start), str(x_coord), str(y_end), str(duration_ms)],
            check=True, capture_output=True, timeout=5
        )
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[ADB] HATA: Kaydırma (swipe) başarısız oldu: {e}")
        return False