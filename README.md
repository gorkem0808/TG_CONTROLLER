# TG_CONTROLLER V001

Raspberry Pi Pico tabanlı arcade controller firmware.

## Sabit pinler

| GP | Görev | USB tuşu |
|---:|---|---|
| GP2 | Coin | 1 |
| GP3 | Player 1 Start | 2 |
| GP4 | Player 1 Tetik | 3 |
| GP5 | Player 1 Bomba | 4 |
| GP6 | Player 2 Start | 5 |
| GP7 | Player 2 Tetik | 6 |
| GP8 | Player 2 Bomba | 7 |
| GP27 | Player 1 Röle | P1 tetikle birlikte |
| GP26 | Player 2 Röle | P2 tetikle birlikte |

Girişler dahili pull-up kullanır. Her buton ilgili GP pini ile GND arasına bağlanır.

## V001 kapsamı

- USB HID klavye
- USB CDC seri bağlantı
- 20 ms buton debounce
- P1/P2 röle kontrolü
- GitHub Actions ile otomatik UF2 üretimi

## GitHub

`Actions → Build TG_CONTROLLER UF2` çalışması tamamlandığında `TG_CONTROLLER_V001_UF2` adlı artifact oluşur.
