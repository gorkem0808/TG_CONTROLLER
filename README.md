# TG_CONTROLLER_PRO V4.2 TRAY HOTFIX

> Sistem tepsisi simgesi doğrulanmadan pencere artık gizlenmez. Program gizliyken EXE tekrar çalıştırılırsa mevcut pencere açılır.

# TG_CONTROLLER_PRO V4.1 HOTFIX

> `psutil` açılış hatası kaldırıldı. Windows Manager artık harici psutil paketine ihtiyaç duymaz ve GitHub'da paketlenmiş EXE self-test başarılı olmadan yayınlanmaz.

## V4 ana proje özellikleri FINAL

Raspberry Pi Pico/RP2040 tabanlı, iki oyunculu potansiyometreli arcade silah sistemi. Paket üç firmware ve tek Windows Manager üretir:

- `TG_CONTROLLER_PRO_CONTROLLER_V4.uf2`
- `TG_CONTROLLER_PRO_GUN_P1_V4.uf2`
- `TG_CONTROLLER_PRO_GUN_P2_V4.uf2`
- `TG_CONTROLLER_PRO_MANAGER_V4.exe`

## Sabit pinler

### Controller Pico

| Pin | Görev | HID |
|---|---|---|
| GP2 | Coin / ortak kredi | `1` |
| GP3 | P1 Start | `2` |
| GP4 | P1 tetik + Röle 1 | `3` basılı kaldığı sürece |
| GP5 | P1 bomba | `4` |
| GP6 | P2 Start | `5` |
| GP7 | P2 tetik + Röle 2 | `6` basılı kaldığı sürece |
| GP8 | P2 bomba | `7` |
| GP27 | Röle 1 | Ayarlanabilir aktif LOW/HIGH |
| GP26 | Röle 2 | Ayarlanabilir aktif LOW/HIGH |

Butonlar dahili pull-up ile çalışır; basınca GND'ye çekilir.

### Her Gun Pico

| Pin | Görev |
|---|---|
| GP26 / ADC0 | X potansiyometre orta bacağı |
| GP27 / ADC1 | Y potansiyometre orta bacağı |
| GP19 | DIP: GND'ye bağlı/ON = silah aktif |
| 3V3(OUT) | Potansiyometre beslemesi |
| GND | Ortak toprak |

## Uygulanan çalışma kuralları

- Manager açıldığında ve sonradan Gun Pico bağlandığında iki silah otomatik pasif edilir.
- F8, P1 ve P2 hareketini birlikte aktif/pasif yapar.
- X düğmesi programı kapatmaz; tepsiye gizler. F8 çalışmaya devam eder.
- Program gerçekten kapatılırsa Gun Pico'lardaki 5 saniyelik geçici pasiflik süresi dolar; GP19 aktif silahlar tekrar aktif olur.
- Her GP19 yalnız kendi silahını etkiler.
- Kalibrasyon tam ekran dört köşedir; merkez adımı yoktur.
- Köşe, ilgili tetik veya normal mouse ile onaylanabilir.
- Her köşede 32 ADC örneği alınır; silah hareket ederse köşe kabul edilmez.
- X/Y tersliği, çapraz bağlantı ve yamuk mekanik geometri gerçek bilinear dört-köşe dönüşümüyle otomatik düzeltilir.
- Kalibrasyon ve ayarlar CRC/sequence kontrollü iki flash sektörüne dönüşümlü yazılır.
- Kalibrasyon sırasında Start, tetik HID'i ve röle çıkışları oyuna gitmez.
- P1 Start + P2 Start 10 saniye kalibrasyon modunu açar; kısa/başarısız ortak basış kredi tüketmez.
- P1/P2 için ayrı 0–10 ivmeli titreme engelleme vardır.
- Ortak kredi havuzu: GP2 +1; P1/P2 Start bir kredi tüketir.
- GP2 kısa basış titreşim rölelerini uyandırır.
- Controller'da 120 saniye hiçbir butona basılmazsa titreşim röleleri uyur; uyurken tetik titreşim motorunu çalıştırmaz.
- Uyku sonrası normal kullanımda röleleri yalnız GP2 kısa coin basışı uyandırır.
- İlgili tetik basılı kaldığı sürece ilgili HID tuşu ve ilgili röle aktif kalır.
- GP2 10 saniye, Controller flash'ında kayıtlı Paradise Lost makrosunu çalıştırır; kısa coin işlemi oluşturmaz.
- Oyun açılış/makro gecikmesi 0–999 saniyedir.
- Cihazlar seri kimliklerine göre otomatik tanınır ve yeniden bağlanır.
- Tek program örneği, sistem tepsisi, Windows başlangıcı, oyun süreç izleme, geri sayım/iptal ve UF2 yükleyici vardır.

## Paradise Lost hakkında dürüst sınırlama

Makro motoru tamamdır; ancak kabindeki gerçek **TEST/BACK, VOL UP/DOWN ve SELECT tuşlarının klavye karşılıkları ve menü adım sayısı doğrulanmadan** bir F1/F2 dizisi otomatik etkinleştirilmez. Manager'daki örnek yalnız JSON biçimini gösterir ve varsayılan olarak kapalıdır. Gerçek sıra kabinde kaydedilip Pico'ya yazıldığında GP2 10 saniye ve otomatik başlangıç aynı doğrulanmış diziyi kullanır.

Ayrıntılar: `docs/PARADISE_LOST_MAKRO.md`.

## Derleme

GitHub Actions, Node.js 24 tabanlı güncel Action ana sürümleriyle çalışır ve sarı Node.js 20 uyarılarını kaldırır. Pico SDK `2.3.0` kullanılır.

Kurulum: `00_BASLA.txt`  
Düzeltme raporu: `docs/EKSIKLER_KAPATMA_RAPORU.md`  
Kabul testi: `docs/TEST_PLANI.md`
