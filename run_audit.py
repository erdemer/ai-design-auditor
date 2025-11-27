# run_audit.py
import sys
import os
import config
import adb_client
import image_analyzer
import comparator  # <-- Artık V8.0
import PIL.Image
from PIL import ImageChops
import report_generator
import argparse
from pprint import pprint


def _crop_image(input_path, crop_top, crop_bottom, output_path):
    """
    Basit crop fonksiyonu: üstten ve alttan belirtilen kadar piksel kırpar.
    """
    if crop_top <= 0 and crop_bottom <= 0:
        return input_path

    try:
        img = PIL.Image.open(input_path)
        width, height = img.size
        top = crop_top
        bottom = height - crop_bottom
        if bottom <= top:
            print(f"[Crop] HATA: Geçersiz crop değerleri: height={height}, top={top}, bottom={bottom}")
            return input_path
        cropped = img.crop((0, top, width, bottom))
        cropped.save(output_path)
        print(f"[Crop] '{input_path}' -> '{output_path}' (top={crop_top}, bottom={crop_bottom})")
        return output_path
    except Exception as e:
        print(f"[Crop] HATA: Resim kırpılırken hata: {e}")
        return input_path


def _images_are_different(img_path_1, img_path_2, diff_threshold=10):
    """
    İki görüntünün anlamlı şekilde farklı olup olmadığını kontrol eder.
    Çok basit bir piksel farkı kıyaslaması yapar.
    """
    if not img_path_1 or not img_path_2:
        return True

    try:
        img1 = PIL.Image.open(img_path_1).convert("RGB")
        img2 = PIL.Image.open(img_path_2).convert("RGB")
        if img1.size != img2.size:
            return True
        diff = ImageChops.difference(img1, img2)
        bbox = diff.getbbox()
        if bbox:
            return True
        else:
            return False
    except Exception as e:
        print(f"[HATA] Görüntü karşılaştırmada hata: {e}")
        return False


def main():
    print("--- AI Design Auditor (v8.0 - XML vs AI-JSON) Başlatılıyor ---")

    # 1. Girdi (Argüman) Kontrolü
    parser = argparse.ArgumentParser(description="AI Tasarım Denetimi Aracı (V10 Hibrit Mod)")

    parser.add_argument(
        "--figma-parts",
        nargs='+',
        required=True,
        help="Karşılaştırılacak Figma PNG parçalarının yolları (Sırayla, örn: part1.png)"
    )
    # --- GÜNCELLENMİŞ ARGÜMAN: Artık .xml dosyaları da olabilir ---
    parser.add_argument(
        "--app-parts",
        nargs='+',
        required=False,
        help="(Opsiyonel) Manuel olarak alınan App SS (.png) VE XML (.xml) parçaları. Eğer verilmezse, ADB kullanılır."
    )

    parser.add_argument(
        "--app-analysis-mode",
        choices=["xml", "ai"],
        default=config.APP_ANALYSIS_MODE,
        help="App tarafını XML (uiautomator) veya AI (görüntü analizi) ile çözümle."
    )

    parser.add_argument("--figma-crop-top", type=int, default=0, help="Figma PNG'lerinden üstten kırpılacak piksel.")
    parser.add_argument("--figma-crop-bottom", type=int, default=0, help="Figma PNG'lerinden alttan kırpılacak piksel.")
    parser.add_argument("--app-crop-top", type=int, default=0,
                        help="TÜM App SS'lerinden üstten kırpılacak piksel (örn: status bar).")
    parser.add_argument("--app-crop-bottom", type=int, default=0,
                        help="TÜM App SS'lerinden alttan kırpılacak piksel (örn: nav bar).")

    args = parser.parse_args()

    # Run Mode belirle
    if args.app_parts:
        run_mode = "manual"
        print("[Mod] 'Manuel Mod' aktif. Sağlanan App dosyaları kullanılacak.")
    else:
        run_mode = "auto"
        print("[Mod] 'Otomatik Mod' (ADB) aktif. ADB başarısız olursa yerel dosyalara bakılacak.")

    final_report = {
        "summary": {"error_count": 0, "layout_success_count": 0, "style_success_count": 0, "warning_count": 0,
                    "audit_count": 0, "total_matched": 0},
        "parts": [],
        "all_warnings": []
    }

    num_parts = len(args.figma_parts)
    last_successful_ss_path = None  # Sadece 'scroll'u algılamak için

    if run_mode == "auto":
        print("\n[Oto-Mod] Başlangıç ekran görüntüsü (Base) alınıyor...")
        last_successful_ss_path = adb_client.take_screenshot(0)
        if not last_successful_ss_path:
            # Fallback (Yedek) mantığı: PNG'yi yerelden ara
            fallback_path = "app_screenshot_part_0.png"
            if os.path.exists(fallback_path):
                print(f"[Oto-Mod] ADB başarısız oldu, fakat yerelde '{fallback_path}' bulundu ve kullanılacak.")
                last_successful_ss_path = fallback_path
            else:
                print("[Oto-Mod] HATA: Ne ADB ne de yerel fallback ekran görüntüsü alınabildi.")
                sys.exit(1)

    for i, figma_part_path in enumerate(args.figma_parts):
        part_index = i
        print(f"\n--- Parça {part_index} işleniyor ---")
        if not os.path.exists(figma_part_path):
            print(f"HATA: Figma parçası '{figma_part_path}' bulunamadı. Atlanıyor.")
            continue

        app_xml_path_for_analysis = None
        app_ss_path_for_report = None

        if run_mode == "manual":
            app_xml_path = args.app_parts[i]
            print(f"   App XML (Manuel): '{app_xml_path}'")
            if not os.path.exists(app_xml_path):
                print(f"HATA: App XML parçası '{app_xml_path}' bulunamadı. Atlanıyor.")
                continue
            app_xml_path_for_analysis = app_xml_path

            # Manuel modda, XML ile aynı isimde bir .png olduğunu varsay
            app_ss_path_for_report = os.path.splitext(app_xml_path)[0] + ".png"
            if not os.path.exists(app_ss_path_for_report):
                print(f"UYARI: Rapor için '{app_ss_path_for_report}' görseli bulunamadı.")
                app_ss_path_for_report = None  # Raporun resimsiz olmasına neden olacak

        else:  # run_mode == "auto"
            if i == 0:
                app_ss_path_for_report = last_successful_ss_path
            else:
                print("[Oto-Scroll] Kaydırma deneniyor...")
                scroll_success = adb_client.scroll_down(args.app_crop_top, args.app_crop_bottom)
                new_ss_path = adb_client.take_screenshot(part_index)

                if not scroll_success or not new_ss_path:
                    # ADB Başarısız -> Fallback'i dene
                    fallback_path = f"app_screenshot_part_{part_index}.png"
                    if os.path.exists(fallback_path):
                        print(f"[Oto-Scroll] ADB başarısız, fakat '{fallback_path}' bulundu ve kullanılacak.")
                        new_ss_path = fallback_path
                    else:
                        print("[Oto-Scroll] HATA: ADB scroll + screenshot başarısız ve fallback görüntü yok. Parça atlanıyor.")
                        continue

                # Görüntü gerçekten farklı mı diye kontrol et (opsiyonel)
                if not _images_are_different(last_successful_ss_path, new_ss_path):
                    print("[Oto-Scroll] UYARI: Yeni ekran görüntüsü bir öncekinden anlamlı derecede farklı değil. Scroll algılanamadı.")
                else:
                    last_successful_ss_path = new_ss_path

                app_ss_path_for_report = new_ss_path

            # Otomatik modda XML dump al
            app_xml_path_for_analysis = adb_client.dump_layout_xml()
            if not app_xml_path_for_analysis:
                fallback_xml = "app_layout_dump.xml"
                if os.path.exists(fallback_xml):
                    print(f"[Oto-Mod] ADB XML dump başarısız, fakat yerelde '{fallback_xml}' bulundu ve kullanılacak.")
                    app_xml_path_for_analysis = fallback_xml
                else:
                    print("[Oto-Mod] HATA: Ne ADB XML dump ne de yerel fallback XML bulundu. Bu parça için layout analizi yapılamayacak.")

        # 2. Adım: Görüntüleri Kırp (Opsiyonel)
        # SADECE AI'ye gidecek olan FIGMA görüntüsünü kırp
        figma_cropped_path = figma_part_path
        if args.figma_crop_top > 0 or args.figma_crop_bottom > 0:
            figma_cropped_path = _crop_image(
                figma_part_path, args.figma_crop_top, args.figma_crop_bottom,
                f"figma_cropped_part_{part_index}.png"
            )
        else:
            print("[Crop] Figma için kırpma atlanıyor (değerler 0).")

        # App SS'ini SADECE RAPORLAMA için kırp
        app_cropped_path_for_report = app_ss_path_for_report
        if app_ss_path_for_report and (args.app_crop_top > 0 or args.app_crop_bottom > 0):
            app_cropped_path_for_report = _crop_image(
                app_ss_path_for_report, args.app_crop_top, args.app_crop_bottom,
                f"app_cropped_part_{part_index}.png"
            )

        if not figma_cropped_path or not app_xml_path_for_analysis:
            print("HATA: Gerekli Figma veya App verisi yok. Bu parça atlanıyor.")
            continue

        # 3. Adım: AI Analizi (SADECE FIGMA)
        figma_data_json = image_analyzer.analyze_image(figma_cropped_path)

        if not figma_data_json:
            print("HATA: AI Figma analizi başarısız. Bu parça atlanıyor.")
            continue

        # 4. Adım: En-boy oranlarına göre scale factor hesapla
        try:
            with PIL.Image.open(figma_cropped_path) as img:
                figma_width = img.width
            # App genişliğini XML'den (root node) veya SS'ten almamız lazım
            # Şimdilik SS'ten alalım
            with PIL.Image.open(app_cropped_path_for_report) as img:
                app_width = img.width
        except Exception as e:
            print(f"HATA: Kırpılmış görüntü boyutları okunurken hata: {e}. Parça atlanıyor.")
            continue

        if args.app_analysis_mode == "ai":
            if not app_cropped_path_for_report:
                print("UYARI: App için kırpılmış ekran görüntüsü bulunamadı, XML moduna düşülüyor.")
                if not app_xml_path_for_analysis:
                    print("HATA: Ne App SS ne de XML mevcut, bu parça atlanıyor.")
                    continue
                results_part = comparator.compare_layouts(
                    figma_data_json,
                    app_xml_path_for_analysis,
                    figma_width,
                    app_width,
                    config.DEFAULT_TOLERANCE_PX
                )
            else:
                app_data_json = image_analyzer.analyze_image(app_cropped_path_for_report)
                if not app_data_json:
                    print("UYARI: AI App analizi başarısız, XML moduna düşülüyor.")
                    if not app_xml_path_for_analysis:
                        print("HATA: App XML de yok, bu parça atlanıyor.")
                        continue
                    results_part = comparator.compare_layouts(
                        figma_data_json,
                        app_xml_path_for_analysis,
                        figma_width,
                        app_width,
                        config.DEFAULT_TOLERANCE_PX
                    )
                else:
                    # --- DEBUG: JSON'ları kaydet ---
                    import json
                    with open(f"debug_figma_part_{part_index}.json", "w") as f:
                        json.dump(figma_data_json, f, indent=2)
                    with open(f"debug_app_part_{part_index}.json", "w") as f:
                        json.dump(app_data_json, f, indent=2)
                    print(f"[Debug] JSON verileri 'debug_figma_part_{part_index}.json' ve 'debug_app_part_{part_index}.json' dosyalarına kaydedildi.")

                    results_part = comparator.compare_layouts_ai(
                        figma_data_json,
                        app_data_json,
                        figma_width,
                        app_width,
                        config.DEFAULT_TOLERANCE_PX
                    )
        else:
            results_part = comparator.compare_layouts(
                figma_data_json,
                app_xml_path_for_analysis,
                figma_width,
                app_width,
                config.DEFAULT_TOLERANCE_PX
            )

        # 5. Adım: Sonuçları Ana Rapora Ekle
        final_report["parts"].append({
            "part_index": part_index,
            "image_pair": {
                "figma": figma_cropped_path,
                "app": app_cropped_path_for_report  # Kırpılmış SS'i rapora yolla
            },
            "figma_spec": figma_data_json,
            "comparison_results": results_part
        })

        # 6. Adım: Global Özeti Güncelle
        part_summary = results_part.get("summary", {})
        final_report["summary"]["error_count"] += part_summary.get("error_count", 0)
        final_report["summary"]["audit_count"] += part_summary.get("audit_count", 0)
        final_report["summary"]["layout_success_count"] += part_summary.get("layout_success_count", 0)
        final_report["summary"]["style_success_count"] += part_summary.get("style_success_count", 0)
        final_report["summary"]["warning_count"] += part_summary.get("warning_count", 0)
        final_report["summary"]["total_matched"] += part_summary.get("total_matched", 0)

        if i == 0:
            final_report["scale_factor"] = results_part.get("scale_factor", 0.0)

    # 7. Adım: Global yüzde uyum hesapları
    summary = final_report.get("summary", {})
    total = summary.get("total_matched", 0) or 0
    if total > 0:
        summary["layout_match_pct"] = round((summary.get("layout_success_count", 0) / total) * 100.0, 1)
        summary["style_match_pct"] = round((summary.get("style_success_count", 0) / total) * 100.0, 1)
        summary["overall_match_pct"] = round(
            ((summary.get("layout_success_count", 0) + summary.get("style_success_count", 0)) / (2 * total)) * 100.0,
            1,
        )
    else:
        summary["layout_match_pct"] = 0.0
        summary["style_match_pct"] = 0.0
        summary["overall_match_pct"] = 0.0

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