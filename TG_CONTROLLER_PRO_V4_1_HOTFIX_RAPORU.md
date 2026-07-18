# TG_CONTROLLER_PRO V4.1 Hotfix Raporu

## Bildirilen hata

```text
ModuleNotFoundError: No module named 'psutil'
```

Hata, Windows Manager açılırken `tg_controller/game.py` dosyasının harici
`psutil` paketini yükleyememesi nedeniyle oluşuyordu.

## Uygulanan kesin düzeltme

1. `psutil` projeden tamamen kaldırıldı.
2. Oyun işlemi kontrolü Python standart kütüphanesi ve Windows
   `CreateToolhelp32Snapshot / Process32FirstW / Process32NextW` API'leriyle
   yeniden yazıldı.
3. `desktop/requirements.txt` dosyasından `psutil` çıkarıldı.
4. PyInstaller komutuna seri port modülleri açıkça eklendi.
5. Manager'a `--self-test` modu eklendi.
6. GitHub Actions, EXE'yi oluşturduktan sonra gerçek olarak
   `--self-test` ile çalıştırır.
7. Self-test başarısız olursa Windows artifact'i yüklenmez.
8. Bu hatanın tekrar eklenmesini engelleyen otomatik test eklendi.

## Firmware durumu

Controller, Player 1 ve Player 2 firmware kodlarında değişiklik yapılmadı.
Daha önce V4 UF2 yüklenmiş Pico'ların yeniden programlanması gerekmez.

## Yeni Windows çıktısı

```text
TG_CONTROLLER_PRO_MANAGER_V4_1.exe
```

## Doğrulama sınırı

Bu ortamda Windows/PyInstaller EXE üretimi yapılamadığı için gerçek EXE testi
GitHub Actions Windows runner üzerinde yapılacaktır. Workflow artık self-test
başarılı olmadan artifact oluşturmayacak şekilde düzenlenmiştir.
