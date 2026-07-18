# Kurulum

## 1. Firmware

Her Pico'ya kendi UF2 dosyasını yükleyin. Yanlış dosya yüklenirse BOOTSEL düğmesiyle tekrar doğru dosyayı kopyalayabilirsiniz.

## 2. İlk açılış

Manager cihazları otomatik tanır. Dashboard'da Controller, Player 1 ve Player 2 için port, sürüm ve canlılık görünmelidir.

Program ilk çalıştırmada mevcut kullanıcı hesabının Windows başlangıcına kendini ekler ve sonraki açılışlarda küçültülmüş başlar. X düğmesi yalnız pencereyi gizler. Bu düzen, ana ekran açık olmasa da F8'in çalışmasını sağlar.

## 3. Kalibrasyon

- P1 Start + P2 Start: 10 saniye.
- P1 veya P2 Start: oyuncu seçimi.
- Sol üst, sağ üst, sağ alt, sol alt.
- Tetik veya normal mouse tıklaması.
- Silah sabit değilse nokta yeniden istenir.
- Dördüncü köşe geçerliyse otomatik flash kaydı ve çıkış.

## 4. TeknoParrot

- Coin: `1`
- P1 Start: `2`
- P1 tetik: `3`
- P1 bomba: `4`
- P2 Start: `5`
- P2 tetik: `6`
- P2 bomba: `7`

P1/P2 Gun aygıtlarını RawInput/absolute lightgun olarak ayrı ayrı seçin.

## 5. Röle

Röle modülünün aktif LOW veya aktif HIGH olduğu yüksüz LED/multimetre ile doğrulanır. Motor/solenoid beslemesi Pico'dan alınmaz. Transistör/MOSFET sürücü ve flyback diyot kullanılır.
