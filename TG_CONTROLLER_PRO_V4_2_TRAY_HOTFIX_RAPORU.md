# TG_CONTROLLER_PRO V4.2 Sistem Tepsisi Hotfix Raporu

## Bildirilen sorun

Program X düğmesiyle gizlendikten sonra Windows saatinin yanında
TG_CONTROLLER_PRO simgesi görünmüyordu. Bu durumda kullanıcı programı yeniden
açamıyordu.

## Kök neden

Eski sürüm `pystray.Icon.run()` işlemini arka plan thread'inde başlatıyor, ancak
başlatma hatasını kontrol etmiyordu. Windows tepsi arka ucu veya paketlenmiş bir
modül yüklenemezse hata `--windowed` EXE içinde görünmeden thread sonlanabiliyordu.
Pencere buna rağmen gizleniyordu.

## Yapılan düzeltmeler

- Tepsi thread'i için hazır/başarısız olayları eklendi.
- Program, tepsi simgesinin gerçekten görünür olduğunu doğruluyor.
- Tepsi başlatılamazsa pencere artık gizlenmiyor.
- Kullanıcıya gerçek tepsi hata mesajı gösteriliyor.
- PyInstaller komutuna `pystray._win32` açıkça eklendi.
- İkinci EXE çalıştırılışı yeni kopya açmak yerine mevcut gizli pencereye
  `Programı Göster` sinyali gönderiyor.
- Gizli pencere öne getirilirken kısa süreli `topmost` uygulanıyor.
- Bu davranışlar için otomatik sözleşme testi eklendi.

## Firmware

Controller ve iki Gun Pico firmware'i değişmedi. Yeniden UF2 yüklemesi gerekmez.
