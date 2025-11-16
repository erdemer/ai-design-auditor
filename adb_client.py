# adb_client.py
import subprocess
import os
import time
import re

# Cihazdaki geçici dosya yolları
DEVICE_TEMP_SS_PATH = "/sdcard/ai_audit_screenshot.png"
DEVICE_TEMP_XML_PATH = "/sdcard/ai_audit_layout.xml"


def _get_screen_dimensions():
    """Cihazın fiziksel ekran boyutlarını 'adb shell wm size' ile alır."""
    try:
        result = subprocess.run(
            ["adb", "shell", "wm", "size"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        match = re.search(r"Physical size: (\\d+)x(\\d+)", output)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
            print(f"[ADB] Ekran boyutu: {width}x{height}")
            return width, height
        else:
            print("[ADB] Ekran boyutu alınamadı, varsayılan 1080x2400 kullanılıyor.")
            return 1080, 2400
    except Exception as e:
        print(f"[ADB] Ekran boyutu okunurken hata: {e}, varsayılan 1080x2400 kullanılıyor.")
        return 1080, 2400


def take_screenshot(part_index=0, output_dir="."):
    """
    ADB ile ekran görüntüsü alır ve local'e çeker.
    """
    local_filename = os.path.join(output_dir, f"app_screenshot_part_{part_index}.png")
    try:
        print(f"[ADB] Ekran görüntüsü alınıyor -> {local_filename}")
        subprocess.run(["adb", "shell", "screencap", "-p", DEVICE_TEMP_SS_PATH], check=True)
        subprocess.run(["adb", "pull", DEVICE_TEMP_SS_PATH, local_filename], check=True)
        return local_filename
    except Exception as e:
        print(f"[ADB] Ekran görüntüsü alınamadı: {e}")
        return None


def dump_layout_xml(output_dir="."):
    """
    ADB ile UIAutomator XML dump alır ve local'e çeker.
    """
    local_xml = os.path.join(output_dir, "app_layout_dump.xml")
    try:
        print("[ADB] UIAutomator layout XML dump alınıyor...")
        subprocess.run(["adb", "shell", "uiautomator", "dump", DEVICE_TEMP_XML_PATH], check=True)
        subprocess.run(["adb", "pull", DEVICE_TEMP_XML_PATH, local_xml], check=True)
        return local_xml
    except Exception as e:
        print(f"[ADB] XML dump alınamadı: {e}")
        return None


def scroll_down(crop_top=0, crop_bottom=0):
    """
    Basit bir 'scroll down' hareketi uygular.
    crop_top / crop_bottom, status/nav bar kırpmalarını hesaba katmak için kullanılabilir.
    """
    width, height = _get_screen_dimensions()

    start_x = width // 2
    start_y = height // 2
    end_y = int(height * 0.2)  # yukarı doğru kaydır

    try:
        print("[ADB] Scroll hareketi gönderiliyor...")
        subprocess.run(
            ["adb", "shell", "input", "swipe", str(start_x), str(start_y), str(start_x), str(end_y), "600"],
            check=True,
        )
        time.sleep(1.0)
        return True
    except Exception as e:
        print(f"[ADB] Scroll hareketi başarısız: {e}")
        return False