# Yakınım · Antalya Yemek Verisi

Bu depo **yalnızca veri toplamak içindir**. Canlı Yakınım uygulamasına ve Vercel dağıtımına bağlanmaz.

## Ne çıkarıyoruz?
- Antalya merkez pilotu: **30.55–30.84 D / 36.80–36.96 K** (coğrafi kutu; ilçe veya kıyı sınırı değildir).
- OSM: `amenity=restaurant`, `cafe`, `fast_food`; ad (varsa), OSM nesne kimliği, koordinat, kategori, menü bağlantısı **adayı**, yol tarifi URL'si.
- Çıktılar: `yemek_mekanlar.csv`, `yemek_mekanlar.geojson`, `ozet.json`.

## İlk veri alma
**Actions → Antalya Yemek Verisini Hazirla → Run workflow** seçin. İş tamamlandığında çalıştırmanın **Artifacts** bölümündeki `antalya-yemek-veri` arşivini indirin. **Otomatik `push` tetikleyicisi kapalıdır**; her değişiklikte 600+ MB veri yeniden indirilmez. Bu işi yalnızca ihtiyaç olduğunda elle çalıştırın. Sonuç paketinde `toplu_test_raporu.json` dosyası da oluşur. Menü/site URL alanlarında Instagram ve Yemeksepeti bağlantıları filtrelenir.

İşlem: Geofabrik Türkiye PBF → Osmium coğrafi ayıklama → OSM yemek etiketi filtresi → GeoJSON → isim/kimlik/koordinat kontrolü → CSV + GeoJSON. Büyük PBF dosyası depoya yüklenmez; yalnız çalışma sırasında tutulur. Çıktılar GitHub Actions artifacts olarak sunulur.

## Veri kalitesi
- Tarihli OSM envanterindeki **1.039**, 27 Temmuz 2026 tarihli geçmiş **harita öğesi** sayısıydı. Yeni veriyle sayı farklı olabilir.
- Harita noktaları OSM node koordinatı veya yol/alan geometrisinden hesaplanan temsil noktasıdır. Binanın **giriş noktası** olmak zorunda değildir.
- Nesne kimliği olmayan/konumu çözümlenemeyen kayıt haritaya eklenmez.
- OSM kimliğiyle tekilleştirme yapılır; isim benzerliğine göre farklı şubeler birleştirilmez.
- Menü etiketi tek başına doğrulama sayılmaz. `menu_url_candidate` araştırma alanıdır; uygulamada otomatik menü gösterimi için kullanılmaz.
- Google puanı, Instagram ve Yemeksepeti entegrasyonu yoktur.
- Veri envanteri işletmenin hâlen açık olduğunu kanıtlamaz.

## Kaynak, telif ve atıf
**© OpenStreetMap contributors** — veritabanı ODbL 1.0. Kaynak: [Geofabrik Türkiye](https://download.geofabrik.de/europe/turkey.html) ve [OSM telif](https://www.openstreetmap.org/copyright). Yeniden dağıtımda atıf, türetilmiş veritabanı yükümlülükleri ve lisans koşulları korunmalıdır.

Çalıştırma hata verirse özet üretildiğini iddia etmeyin. Önce Actions günlüklerini kontrol edin.
