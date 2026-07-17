# TG_CONTROLLER V005

Controller, Player 1 ve Player 2 aynı sürümde birlikte derlenir.

## GitHub çıktıları

UF2 paketi:

- `TG_CONTROLLER_V005.uf2`
- `TG_GUN_P1_V005.uf2`
- `TG_GUN_P2_V005.uf2`
- `SHA256SUMS.txt`

Windows paketi:

- `TG_CONTROLLER_MANAGER_V005.exe`
- `SHA256SUMS_WINDOWS.txt`

## Gun bağlantıları

Her iki Gun Pico için bağlantı aynıdır:

| Pico pini | Görev |
|---|---|
| GP26 / ADC0 | X potansiyometresi orta uç |
| GP27 / ADC1 | Y potansiyometresi orta uç |
| 3V3 OUT | Potansiyometre besleme |
| GND | Ortak şase |

Tetikler ana Controller üzerinde kalır:

- P1 tetik: Controller GP4
- P2 tetik: Controller GP7

## V005 testi

1. Controller UF2'yi ana Pico'ya yükle.
2. P1 UF2'yi Player 1 Pico'ya yükle.
3. P2 UF2'yi Player 2 Pico'ya yükle.
4. Manager V005'i aç.
5. Üç ayrı COM portu doğru cihaz alanlarına seç.
6. Controller tuşlarını, iki röleyi ve her iki silahın X/Y değerlerini test et.
7. İki gun için Hareket Aç / Hareket Kapat komutlarını test et.

Kalibrasyon V006 kapsamındadır.
