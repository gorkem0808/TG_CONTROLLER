# TG_CONTROLLER V004

V004 ile Player 1 Gun Pico desteği eklendi.

## Üretilen dosyalar

- `TG_CONTROLLER_V004.uf2`
- `TG_GUN_P1_V004.uf2`
- `TG_CONTROLLER_MANAGER_V004.exe`

## Player 1 bağlantıları

| Pico pini | Görev |
|---|---|
| GP26 / ADC0 | X potansiyometresi orta uç |
| GP27 / ADC1 | Y potansiyometresi orta uç |
| 3V3 OUT | Potansiyometre besleme |
| GND | Ortak şase |

Tetik Player 1 Pico'ya bağlanmaz. P1 tetik ana Controller GP4 üzerinde kalır.

## V004 kapsamı

- Ham X/Y ADC okuma
- Player 1 USB cihaz kimliği
- USB CDC haberleşme
- Player 1 canlı X/Y Manager ekranı
- Mouse hareketini aç/kapat komutları
- Henüz dört köşe kalibrasyonu yoktur
