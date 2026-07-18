# TG_CONTROLLER_PRO V4.3 — Sabit Makro ve Buton Kilidi Raporu

## Sabit Paradise Lost makrosu

```text
345455535455535455335555555544
```

Tuş eşlemesi:

```text
3 = F1
4 = F2
5 = AŞAĞI
```

Makro 30 adımdır. Firmware içine sabitlenmiştir. Manager üzerinden
değiştirilemez, silinemez veya başka dizi yüklenemez.

## Açılış güvenlik sırası

```text
Controller açılır
→ GP3–GP8 oyun butonları ve iki titreşim rölesi kilitli
→ Oyun açılır
→ Manager'da ayarlanan 0–999 saniye beklenir
→ Sabit makro çalışır
→ Makro tamamlanınca sistem kredi bekler
→ GP2 kısa coin basışı kredi yollar
→ GP3–GP8 butonları ve tetik röleleri kullanılabilir olur
```

Butonlar kredi anında basılıysa yanlış komut oluşmaması için önce tüm oyun
butonlarının bırakılması gerekir. Bırakıldıktan sonra yeni basışlar kabul edilir.

## GP9

Controller Pico üzerindeki GP9 özel makro butonudur.

```text
GP9 kısa basış
→ Otomatik sayaç beklenmez
→ Sabit makro hemen başlar
→ Makro sonunda yeni kredi beklenir
```

GP9 artık klavye `8` göndermez; yalnız sabit Paradise Lost makrosunu çalıştırır.

## Korunan davranışlar

- GP2'ye 10 saniye basmak da makroyu çalıştırır.
- İlgili tetik basılı kaldığı sürece ilgili HID tetik tuşu ve röle aktif kalır.
- 120 saniye hareketsizlikte titreşim röleleri uyur.
- Kalibrasyon, GP19, F8, titreme filtresi ve ortak kredi sistemi korunur.
