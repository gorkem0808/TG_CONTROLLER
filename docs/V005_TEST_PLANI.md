# TG_CONTROLLER V005 Test Planı

## Derleme kabulü
- Build 3 UF2 Files: yeşil
- Build Windows Manager: yeşil
- Üç UF2'nin boyutu sıfırdan büyük
- EXE oluşmuş

## Controller testi
- GP2..GP8 klavye 1..7
- GP4 basılıyken Röle 1
- GP7 basılıyken Röle 2
- Manager canlı tuş durumları
- Manager röle testleri

## Player 1
- USB adı TG GUN PLAYER 1
- X/Y 0..4095 arasında değişiyor
- MOTION ON/OFF çalışıyor

## Player 2
- USB adı TG GUN PLAYER 2
- X/Y 0..4095 arasında değişiyor
- MOTION ON/OFF çalışıyor

## Birlikte çalışma
- Üç Pico aynı anda bağlı
- P1 ve P2 ayrı COM port
- P1 hareketi P2 değerlerini etkilemiyor
- Controller tuşları silah haberleşmesini bozmuyor
