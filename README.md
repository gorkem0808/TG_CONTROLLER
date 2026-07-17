# TG_CONTROLLER V002

Raspberry Pi Pico tabanlı arcade controller ve Windows yönetim programı.

## Pinler

| GP | Görev | HID |
|---|---|---|
| GP2 | Coin | 1 |
| GP3 | P1 Start | 2 |
| GP4 | P1 Tetik | 3 |
| GP5 | P1 Bomba | 4 |
| GP6 | P2 Start | 5 |
| GP7 | P2 Tetik | 6 |
| GP8 | P2 Bomba | 7 |
| GP27 | P1 Röle | — |
| GP26 | P2 Röle | — |

## V002 yenilikleri

- USB CDC üzerinden cihaz tanıma
- Canlı buton ve röle durum paketleri
- Windows yönetim programı
- Röle 1 ve Röle 2 için güvenli 250 ms test darbesi
- GitHub Actions ile UF2 ve Windows EXE üretimi

## GitHub çıktıları

- `TG_CONTROLLER_V002.uf2`
- `TG_CONTROLLER_MANAGER_V002.exe`
