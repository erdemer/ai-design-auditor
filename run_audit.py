# run_audit.py
import sys
import os
import config
import adb_client
import image_analyzer
import comparator
import PIL.Image
from PIL import ImageChops
import report_generator
import argparse
from pprint import pprint


# import json # Artık debug için gerekmiyor

def _crop_image(image_path, top_px, bottom_px, output_path):
    """
    Bir görüntüyü üstten ve alttan kırpar ve yeni bir dosyaya kaydeder.
    """
    try:
        with PIL.Image.open(image_path) as img:
            width, height = img.size

            left = 0
            top = top_px
            right = width
            bottom = height - bottom_px

            if top >= bottom:
                print(f"HATA: Kırpma değerleri geçersiz. 'top' ({top}) 'bottom'dan ({bottom}) büyük olamaz.")
                return None

            print(f"[Crop] '{image_path}' kırpılıyor: Üstten {top_px}px, Alttan {bottom_px}px.")
            cropped_img = img.crop((left, top, right, bottom))
            cropped_img.save(output_path)
            print(f"[Crop] Kırpılmış görüntü '{output_path}' olarak kaydedildi.")
            return output_path

    except Exception as e:
        print(f"HATA: Görüntü kırpılırken hata oluştu: {e}")
        return None


def _images_are_identical(path1, path2):
    """İki görüntü dosyasının piksel piksel aynı olup olmadığını kontrol eder."""
    try:
        img1 = PIL.Image.open(path1)
        img2 = PIL.Image.open(path2)

        if img1.size != img2.size:
            return False

        diff = ImageChops.difference(img1.convert('RGB'), img2.convert('RGB'))

        if diff.getbbox() is None:
            return True
        else:
            return False
    except Exception as e:
        print(f"[HATA] Görüntü karşılaştırmada hata: {e}")
        return False


def main():
    print("--- AI Design Auditor (v4.3 - Hibrit Mod / Hata Düzeltmeli) Başlatılıyor ---")

    # 1. Girdi (Argüman) Kontrolü
    parser = argparse.ArgumentParser(description="AI Tasarım Denetimi Aracı (Hibrit Mod)")

    parser.add_argument(
        "--figma-parts",
        nargs='+',
        required=True,
        help="Karşılaştırılacak Figma PNG parçalarının yolları (Sırayla, örn: part1.png part2.png)"
    )
    parser.add_argument(
        "--app-parts",
        nargs='+',
        required=False,
        help="(Opsiyonel) Manuel olarak alınan App SS parçaları. Eğer verilmezse, ADB kullanılır."
    )

    parser.add_argument("--figma-crop-top", type=int, default=0, help="Figma PNG'lerinden üstten kırpılacak piksel.")
    parser.add_argument("--figma-crop-bottom", type=int, default=0, help="Figma PNG'lerinden alttan kırpılacak piksel.")
    parser.add_argument("--app-crop-top", type=int, default=0,
                        help="TÜM App SS'lerinden üstten kırpılacak piksel (örn: status bar).")
    parser.add_argument("--app-crop-bottom", type=int, default=0,
                        help="TÜM App SS'lerinden alttan kırpılacak piksel (örn: nav bar).")

    args = parser.parse_args()

    # Çalışma Modu Kontrolü
    run_mode = "auto"
    if args.app_parts:
        run_mode = "manual"
        print("[Mod] 'Manuel Mod' aktif. Sağlanan App SS dosyaları kullanılacak.")
        if len(args.figma_parts) != len(args.app_parts):
            print(f"HATA: Parça sayıları eşleşmiyor!")
            print(f"   Figma Parçaları: {len(args.figma_parts)} adet")
            print(f"   App Parçaları:   {len(args.app_parts)} adet")
            sys.exit(1)
    else:
        print("[Mod] 'Otomatik Mod' (ADB) aktif. ADB başarısız olursa yerel dosyalara bakılacak.")

    final_report = {
        "summary": {"error_count": 0, "success_count": 0, "warning_count": 0, "audit_count": 0},
        "parts": [],
        "all_warnings": []
    }

    num_parts = len(args.figma_parts)
    last_successful_ss_path = None

    if run_mode == "auto":
        print("\n[Oto-Mod] Başlangıç ekran görüntüsü (Base) alınıyor...")
        last_successful_ss_path = adb_client.take_screenshot(0)

        if not last_successful_ss_path:
            print("[ADB Hatası] Başlangıç SS'i alınamadı.")
            fallback_path = "app_screenshot_part_0.png"
            if os.path.exists(fallback_path):
                print(f"[Fallback] Yerel dosya bulundu: '{fallback_path}'. Analiz için bu kullanılacak.")
                last_successful_ss_path = fallback_path
            else:
                print(f"HATA: ADB başarısız VE yerel dosya '{fallback_path}' bulunamadı.")
                sys.exit(1)

    # --- ANA DÖNGÜ ---
    for i, figma_part_path in enumerate(args.figma_parts):

        part_index = i + 1
        print(f"\n--- PARÇA {part_index} / {num_parts} İŞLENİYOR ---")
        print(f"   Figma: '{figma_part_path}'")

        if not os.path.exists(figma_part_path):
            print(f"HATA: Figma parçası '{figma_part_path}' bulunamadı. Atlanıyor.")
            continue

        current_ss_path_for_analysis = None

        if run_mode == "manual":
            app_part_path = args.app_parts[i]
            print(f"   App (Manuel): '{app_part_path}'")
            if not os.path.exists(app_part_path):
                print(f"HATA: App parçası '{app_part_path}' bulunamadı. Atlanıyor.")
                continue
            current_ss_path_for_analysis = app_part_path

        else:  # run_mode == "auto"
            if i == 0:
                current_ss_path_for_analysis = last_successful_ss_path
            else:
                print("[Oto-Scroll] Kaydırma deneniyor...")
                scroll_success = adb_client.scroll_down(args.app_crop_top, args.app_crop_bottom)
                new_ss_path = adb_client.take_screenshot(part_index)

                if not scroll_success or not new_ss_path:
                    print("[ADB Hatası] Kaydırma veya SS alma başarısız.")
                    fallback_path = f"app_screenshot_part_{part_index}.png"
                    if os.path.exists(fallback_path):
                        print(f"[Fallback] Yerel dosya bulundu: '{fallback_path}'. Analiz için bu kullanılacak.")
                        new_ss_path = fallback_path
                    else:
                        print(f"HATA: ADB başarısız VE yerel dosya '{fallback_path}' bulunamadı.")
                        break

                if _images_are_identical(last_successful_ss_path, new_ss_path):
                    print("\n[Oto-Scroll] HATA: Sayfanın sonuna ulaşıldı!")
                    final_report["all_warnings"].append(
                        f"Oto-Scroll HATA: App sayfanın sonuna ulaştı (Parça {part_index - 1} -> {part_index}), "
                        f"ancak {num_parts - i} adet Figma parçası daha vardı."
                    )
                    break

                print("[Oto-Scroll] Kaydırma başarılı, ekran değişti.")
                last_successful_ss_path = new_ss_path
                current_ss_path_for_analysis = new_ss_path

            print(f"   App (Oto/Fallback): '{current_ss_path_for_analysis}'")

        # 2. Adım: Görüntüleri Kırp (Opsiyonel)
        figma_cropped_path = figma_part_path
        if args.figma_crop_top > 0 or args.figma_crop_bottom > 0:
            figma_cropped_path = _crop_image(
                figma_part_path, args.figma_crop_top, args.figma_crop_bottom,
                f"figma_cropped_part_{part_index}.png"
            )
        else:
            print("[Crop] Figma için kırpma atlanıyor (değerler 0).")

        app_cropped_path = current_ss_path_for_analysis
        if args.app_crop_top > 0 or args.app_crop_bottom > 0:
            app_cropped_path = _crop_image(
                current_ss_path_for_analysis, args.app_crop_top, args.app_crop_bottom,
                f"app_cropped_part_{part_index}.png"
            )
        else:
            print("[Crop] App için kırpma atlanıyor (değerler 0).")

        if not figma_cropped_path or not app_cropped_path:
            print("HATA: Kırpma işlemi başarısız. Bu parça atlanıyor.")
            continue

        # 3. Adım: AI Eşleştirme ve Analiz
        matched_pairs_json = image_analyzer.analyze_image_pair(figma_cropped_path, app_cropped_path)

        # --- DEBUG KODU SİLİNDİ ---
        # Artık 'comparator'a gitmeden önce durmuyoruz.
        # --- BİTTİ ---

        if not matched_pairs_json:
            print("HATA: AI eşleştirme analizi başarısız. Bu parça atlanıyor.")
            final_report["all_warnings"].append(f"UYARI: Parça {part_index} AI tarafından analiz edilemedi.")
            continue

        # 4. Adım: Karşılaştır
        print(f"[Karşılaştırma] Parça {part_index} karşılaştırılıyor...")
        try:
            with PIL.Image.open(figma_cropped_path) as img:
                figma_width = img.width

            # --- HATA DÜZELTMESİ (v4.3) ---
            with PIL.Image.open(app_cropped_path) as img:
                app_width = img.width  # 'img.img.width' DÜZELTİLDİ
            # --- DÜZELTME BİTTİ ---

        except Exception as e:
            print(f"HATA: Kırpılmış görüntü boyutları okunurken hata: {e}. Parça atlanıyor.")
            continue

        results_part = comparator.compare_layouts(
            matched_pairs_json, figma_width, app_width, config.DEFAULT_TOLERANCE_PX
        )

        # 5. Adım: Sonuçları Ana Rapora Ekle
        final_report["parts"].append({
            "part_index": part_index,
            "image_pair": {
                "figma": figma_cropped_path,
                "app": app_cropped_path
            },
            "comparison_results": results_part
        })

        # 6. Adım: Global Özeti Güncelle
        part_summary = results_part.get("summary", {})
        final_report["summary"]["error_count"] += part_summary.get("error_count", 0)
        final_report["summary"]["audit_count"] += part_summary.get("audit_count", 0)
        final_report["summary"]["success_count"] += part_summary.get("layout_success_count",
                                                                     0)  # layout_success_count'u kullanalım
        final_report["summary"]["style_success_count"] = part_summary.get("style_success_count",
                                                                          0)  # (Bu, bir sonraki sürümde güncellendi)
        final_report["summary"]["warning_count"] += part_summary.get("warning_count", 0)
        final_report["all_warnings"].extend(results_part.get("warnings", []))

        if i == 0:
            final_report["scale_factor"] = results_part.get("scale_factor", 0.0)

    # --- DÖNGÜ BİTTİ ---

    # 7. Adım: Final Raporunu Oluştur
    print("\n--- TÜM PARÇALAR İŞLENDİ. FİNAL RAPORU OLUŞTURULUYOR ---")

    report_generator.create_html_report(final_report)

    print("-----------------------------------------------------")

    if "summary" in final_report and final_report["summary"].get("error_count", 0) > 0:
        print(f"\nDurum: BAŞARISIZ ({final_report['summary']['error_count']} toplam hata bulundu)")
    elif "summary" not in final_report:
        print("\nDurum: BELİRSİZ (Rapor özeti oluşturulamadı)")
    else:
        print("\nDurum: BAŞARILI (Kritik layout hatası bulunmadı)")


if __name__ == "__main__":
    main()