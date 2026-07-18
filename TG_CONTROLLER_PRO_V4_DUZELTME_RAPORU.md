# TG_CONTROLLER_PRO V4 FINAL — Eksikler Kapatma Raporu

Tarih: 17 Temmuz 2026  
Sürüm: 4.0.0

Bu rapor, önceki V2/V3 incelemesinde bulunan eksikleri ve kullanıcının konuşmalarda istediği çalışma kurallarını tek tek karşılaştırır.

## Sonuç özeti

- **Yazılım ve firmware içinde kapatılan maddeler:** 28
- **GitHub/yerel otomatik doğrulamaya alınan maddeler:** Python sözdizimi, birim testleri, statik sözleşme testleri, ARM derlemesi, firmware boyutu, SHA-256
- **Kabin üzerinde doğrulanması gereken tek dış bilgi:** Paradise Lost operatör menüsünün gerçek tuş sırası

Gerçek servis tuş sırası bilinmediği için tahmini F1/F2 dizisi etkinleştirilmemiştir. Makro motoru, editörü, doğrulaması, Pico flash kaydı, GP2 10 saniye tetiklemesi, açılış gecikmesi ve ilerleme takibi tamamdır.

---

## 1. Paradise Lost Credits Per Play: 4 → 1 makrosu

**Önceki durum:** Firmware içinde gerçek olmayan sabit F1/F2 örneği vardı.  
**V4 düzeltmesi:**

- Sabit tahmini makro kaldırıldı.
- Manager'da doğrulanan JSON makro editörü eklendi.
- En fazla 32 adım, tuş/bekleme sınırları ve toplam 15 dakika doğrulaması eklendi.
- Makro Controller Pico'nun çift sektörlü flash ayarına yazılıyor.
- GP2 10 saniye ve otomatik oyun başlangıcı aynı kayıtlı makroyu çalıştırıyor.
- İlerleme `START / STEP / DONE / STOPPED` olarak görünür.
- Örnek F1/F2 varsayılan kapalıdır ve açık uyarı verir.

**Durum:** Yazılım altyapısı **TAMAM**. Gerçek kabin tuş sırası **SAHA DOĞRULAMASI BEKLİYOR**.

## 2. Oyun yolunun programa eklenmesi

**İstenen yol:** `C:\ArcadeGames\paradiselost\Farcry_R.exe`  
**V4:** Varsayılan ayara doğrudan eklendi; çalışma klasörü de `C:\ArcadeGames\paradiselost`.

**Durum:** **TAMAM**

## 3. Windows açılış otomasyonu

- Program mevcut kullanıcı için Windows Run anahtarına kaydolur.
- İlk varsayılan `windows_autostart=true`.
- `--minimized` ile gizli/tepsi modunda başlar.
- İstenirse Windows açılınca oyunu otomatik açar.
- Üç Pico canlı değilse oyun başlatmayı bekletebilir.

**Durum:** **TAMAM**

## 4. Program penceresi açık değilken F8

- X düğmesi işlemi sonlandırmaz; pencereyi tepsiye gizler.
- F8 global hotkey olarak işlem açıkken her yerde çalışır.
- Windows başlangıcında gizli başladığı için normal kullanımda ana ekran açılmadan F8 kullanılabilir.
- Sistem tepsisinde Göster / F8 / Tamamen Kapat menüsü vardır.
- Gerçekten işlem Görev Yöneticisiyle öldürülürse PC klavyesini dinleyecek bir işlem kalmayacağından F8 teknik olarak çalışamaz; bunun güvenli çözümü resident/autostart uygulamasıdır ve V4 bunu uygular.

**Durum:** **TAMAM — resident servis modeli**

## 5. Kalibrasyon seçerken kredi düşmesi / Start gitmesi

- Controller `maintenance_mode` kullanır.
- P1+P2 Start ortak basışı görüldüğü anda normal Start olayları bastırılır.
- 10 saniye tamamlandığında bakım modu açılır.
- Oyuncu seçimi sırasında Start HID'i ve kredi tüketimi kapalıdır.

**Durum:** **TAMAM**

## 6. 10 saniye sonunda tuşları bırakınca yanlış Start gönderilmesi

- `start_pair_seen` kilidi iki Start tamamen bırakılana kadar aktif kalır.
- Uzun/kısa ortak basış sonrası P1/P2 Start darbesi üretilmez.

**Durum:** **TAMAM**

## 7. Kalibrasyon tetiğinin oyuna ateş/röle göndermesi

- Bakım modunda Controller klavye raporları ve iki röle çıkışı bastırılır.
- Tetik durumu yalnız seri STATUS içinde Manager'a gider.
- Manager seçili oyuncunun tetik yükselen kenarında Gun Pico'ya `CAL CAPTURE` gönderir.

**Durum:** **TAMAM**

## 8. Gerçek dört köşe dönüşümü

- Eski min/max ortalama eşlemesi yerine dört köşe bilinear inverse dönüşümü kullanılır.
- Çapraz X/Y bağlantısı, ters yön ve yamuk mekanik geometri aynı dönüşümle çözülür.
- Durum ekranında otomatik `SWAP / INVX / INVY` bilgisi raporlanır.

**Durum:** **TAMAM**

## 9. Kalibrasyon doğrulaması

Kontroller:

- minimum kenar uzunluğu,
- minimum dörtgen alanı,
- kesişen/yanlış köşe sırası,
- kenar dengesi,
- kalite puanı,
- 120 saniye zaman aşımı,
- eski kalibrasyonu koruma.

**Durum:** **TAMAM**

## 10. Tetik anında tek ADC örneği kullanılması

- Her köşe için 32 örnek alınır.
- En küçük ve en büyük örnek atılarak ortalama hesaplanır.
- X veya Y örnek yayılımı 120 ADC sayımını aşarsa `CALUNSTABLE` gönderilir.
- Aynı köşe yeniden istenir; işlem ilerlemez.

**Durum:** **TAMAM**

## 11. Test sırasında silah imleçlerinin görünmesi

- Canlı Silah Testi sekmesi seri X/Y verisinden ayrı P1 ve P2 nişangâhı çizer.
- Windows HID mouse'unu açmak zorunda değildir.
- Normal ayar ekranında bu nişangâhlar görünmez.

**Durum:** **TAMAM**

## 12. Tetik tuşunun basılı tutulmaması

- P1 tetik basılı olduğu sürece klavye `3` raporda tutulur.
- P2 tetik basılı olduğu sürece klavye `6` raporda tutulur.
- İlgili röle de, sistem uyanıksa, aynı fiziksel basış süresince aktif kalır.

**Durum:** **TAMAM**

## 13. Bomba davranışı

- Bomba, coin ve Start her fiziksel basış için tek ayarlanabilir HID darbesidir.
- Basılı tutma tekrar üretmez.

**Durum:** **TAMAM**

## 14. İki dakikalık röle uykusunun görünmemesi

- Controller STATUS: `RELAYAWAKE=0/1`.
- Dashboard ve Controller ekranında `AKTİF` veya `UYKUDA — kredi bekliyor` gösterilir.

**Durum:** **TAMAM**

## 15. Röle uyku test düğmeleri

Manager'da:

- Röleleri Uyut,
- Röleleri Uyandır,
- Krediyi Sıfırla

düğmeleri bulunur.

**Durum:** **TAMAM**

## 16. Röle aktif LOW/HIGH seçimi

- Manager'dan seçilir.
- Controller flash belleğine kaydedilir.
- Röleler polarite değişiminde önce güvenli kapalı konuma çekilir.

**Durum:** **TAMAM**

## 17. Program açılınca pasifliğin COM bağlantısına bağlı kalması

- COM portları elle seçilmez.
- Device Manager tüm seri portları tarar, `INFO NAME=` kimliğiyle Controller/P1/P2'yi tanır.
- Bir Gun Pico ilk kez veya yeniden bağlandığında hemen `MOTION OFF` alır.
- Pasiflik kirası 2 saniyede bir yenilenir.

**Durum:** **TAMAM**

## 18. Yanlış COM portu seçimi

- Manuel COM seçimi kaldırıldı.
- Üç rol firmware kimliğiyle otomatik eşleştirilir.
- Aynı rolün ikinci kopyası geldiğinde eski bağlantı kapatılıp rol tekilleştirilir.

**Durum:** **TAMAM**

## 19. Firmware ekranının yalnız isim göstermesi

- Manager doğru Pico'ya `BOOTSEL` komutu gönderir.
- `RPI-RP2` sürücüsünü `INFO_UF2.TXT` ile algılar.
- Seçilen UF2'yi sürücüye kopyalar.
- İlerleme ve hata Manager'da görünür.

**Durum:** **TAMAM**

## 20. Eski V2 firmware isimleri

- Bütün kullanıcıya görünen adlar V4 olarak düzeltildi.

**Durum:** **TAMAM**

## 21. Eski dosyalarla kirli ZIP

- V4 paketi sıfırdan temiz dizinde oluşturuldu.
- V1/V2/V3 yükleme belgeleri ve eski workflow kopyaları bulunmaz.

**Durum:** **TAMAM**

## 22. Yama üstüne yama Manager yapısı

Manager parçaları ayrıldı:

- `config.py`
- `device_manager.py`
- `firmware_loader.py`
- `game.py`
- `macro.py`
- `single_instance.py`
- `startup.py`
- `tray.py`
- `ui.py`
- `app.py`

**Durum:** **TAMAM**

## 23. Modüler V3 sözü

V4'te modüler uygulama gerçek olarak uygulanmıştır; tek dev `app.py` kullanılmaz.

**Durum:** **TAMAM**

## 24. Sistem tepsisi

- Göster,
- F8 aktif/pasif,
- Tamamen kapat

menüsü vardır.

**Durum:** **TAMAM**

## 25. Aynı programın iki defa açılması

- Windows named mutex kullanılır.
- İkinci örnek açılmaz ve kullanıcıya zaten çalıştığını bildirir.

**Durum:** **TAMAM**

## 26. Makro ilerleme durumu

- Geri sayım,
- Controller'a gönderim,
- START,
- adım N/toplam,
- DONE,
- STOPPED,
- hata/iptal

Manager'da gösterilir.

**Durum:** **TAMAM**

## 27. Geri sayım ve iptal

- 0–999 saniye.
- Her saniye kalan süre gösterilir.
- İptal düğmesi vardır.
- Oyun kapanırsa makro başlamaz.

**Durum:** **TAMAM**

## 28. Oyun zaten açıksa ikinci kopya açılması

- `psutil` ile EXE adı/tam yol kontrol edilir.
- Oyun zaten açıksa ikinci kopya açılmaz.
- İstenirse yalnız geri sayım/makro başlatılır.
- Oyun kapanışı izlenir; ayar açıksa belirtilen sürede yeniden açılır.

**Durum:** **TAMAM**

---

## İlave güvenlik ve kararlılık düzeltmeleri

- Controller ve her Gun ayarı iki ayrı 4 KiB flash sektörüne sıra numarası/checksum ile dönüşümlü yazılır.
- Yeni kalibrasyon flash yazımı başarısız olursa RAM'de de önceki ayara geri dönülür.
- USB umount/suspend durumunda röleler kapatılır.
- Bakım modu 180 saniyede fail-safe kapanır.
- Gun kalibrasyonu 120 saniyede zaman aşımına uğrar.
- Gun geçici yazılımsal pasifliği 5 saniyelik kirasıdır; Manager çökerse kalıcı kilit oluşmaz.
- Firmware `.bin` boyutları, flash sonundaki 8192 bayt ayar alanına taşmaması için Actions'ta kontrol edilir.
- Bozuk Windows ayar dosyası `.invalid.json` olarak korunur ve güvenli varsayılan açılır.
- UI olay kuyruğu ve log görünümü sınırlandırılır.
- Modern GitHub Action sürümleri kullanılarak eski Node.js 20 uyarıları giderilir.

## Yayın öncesi doğrulama durumu

| Kontrol | Durum |
|---|---|
| Python compileall | Otomatik |
| Python unittest | Otomatik |
| Proje sözleşme testleri | Otomatik |
| Pico SDK ARM derlemesi | GitHub Actions / yerel doğrulama |
| Firmware flash boyut sınırı | Otomatik |
| SHA-256 | Otomatik |
| Gerçek buton/ADC/röle testleri | Kabin testi gerekli |
| Paradise Lost gerçek makro sırası | Kabin ölçümü gerekli |

## Final değerlendirme

V4 kaynak paketinde kullanıcının tarif ettiği kontrol, kalibrasyon, F8, GP19, ortak kredi, tetik/röle, iki dakikalık uyku, oyun başlatma, makro altyapısı, otomatik cihaz tanıma, arka plan çalışma ve firmware yönetimi tamamlanmıştır.

**“Credits Per Play: 4 → 1” işleminin gerçek tuş dizisi yazılım hatası değildir; kabindeki eşlemeyi görmeden güvenli şekilde üretilemeyen tek saha verisidir.** Bu sıra verildiğinde firmware veya Manager mimarisi yeniden yazılmayacak; yalnız Manager'daki makro JSON'u kaydedilip Pico'ya yüklenecektir.
