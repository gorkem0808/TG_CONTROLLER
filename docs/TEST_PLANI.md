# V4 Kabul Test Planı

## Program

- EXE hatasız açılır.
- İkinci EXE açılmaz; zaten çalıştığı bildirilir.
- X ile pencere gizlenir, tepsi simgesi kalır.
- F8 pencere gizliyken iki silahı birlikte değiştirir.
- Tam çıkışta iki Gun Pico `MOTION ON` alır.
- USB sök/tak sonrası roller otomatik bulunur.

## Kalibrasyon

Her oyuncu için:

1. Start 1 + Start 2'yi 9 saniye tutup bırakın: kalibrasyon açılmamalı, kredi düşmemeli, Start oyuna gitmemeli.
2. 10 saniye tutun: bakım modu açılmalı, röleler kapanmalı.
3. P1/P2 Start ile oyuncu seçin: kredi düşmemeli.
4. Kalibrasyonda tetik oyuna `3/6` göndermemeli ve röle çekmemeli.
5. Köşede silahı hareket ettirin: `CALUNSTABLE` ile aynı köşe tekrar istenmeli.
6. Dört köşeyi doğru sırada tamamlayın: kalite puanı ve otomatik kayıt görünmeli.
7. USB/elektrik kesip açın: kalibrasyon korunmalı.
8. Yanlış/kesişen köşe sırası: eski kalibrasyon korunmalı.

## Röle ve giriş

- GP2 kısa basış tam bir coin/kredi üretmeli; basılı tutma tekrar üretmemeli.
- GP2 10 saniye makroyu tetiklemeli ve kredi üretmemeli.
- P1 tetik basılı sürece klavye `3` ve Röle 1 aktif olmalı.
- P2 tetik basılı sürece klavye `6` ve Röle 2 aktif olmalı.
- Röleler uykudayken tetik HID çalışmalı fakat titreşim rölesi çalışmamalı.
- GP2 kısa basış röleleri uyandırmalı.
- 120 saniye hiçbir Controller butonu kullanılmazsa röleler uyumalı.
- Aktif LOW/HIGH ayarı gerçek modülle eşleşmeli.

## Oyun/makro

- Varsayılan EXE yolu doğru olmalı.
- Oyun zaten açıksa ikinci kopya açılmamalı.
- 0, 350 ve 999 saniye ayarları kaydedilip geri yüklenmeli.
- Geri sayım iptal edilebilmeli.
- Oyun kapanınca makro iptal edilmeli.
- Doğrulanmamış/boş makro etkinleştirilememeli.
- Doğrulanmış makro en az 10 soğuk açılışta doğru 1-credit değerini seçmeli.

## Uzun süre

- 8 saat açık test.
- En az 1000 tetik çevrimi önce yüksüz, sonra güvenli gerçek yükle.
- USB hub sök/tak.
- Seri port 10 saniye sessizlik ve yeniden bağlanma.
- UI/log kuyrukları sınırsız büyümemeli.
