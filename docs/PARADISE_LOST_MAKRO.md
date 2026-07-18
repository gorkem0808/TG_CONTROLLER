# Paradise Lost — Credits Per Play Değerini 4’ten 1’e İndirme Makrosu

## Hazır olan bölüm

- Varsayılan oyun yolu: `C:\ArcadeGames\paradiselost\Farcry_R.exe`
- Oyun zaten açıksa ikinci kopya açılmaz.
- Bekleme süresi: `0–999 saniye`.
- Geri sayım ekranda görünür ve iptal edilebilir.
- Oyun geri sayım sırasında kapanırsa makro başlamaz.
- Doğrulanmış makro Controller Pico flash'ına yazılır.
- GP2 kısa basış coin; GP2 10 saniye makro tetikleme olarak ayrılmıştır.
- Makro ilerlemesi adım/adım Manager'da görünür.
- Makro durdurulursa basılı makro tuşu bırakılır.

## Neden hazır bir F1/F2 sırası zorlanmıyor?

Paradise Lost servis menüsünün kabin kartındaki fiziksel kontrolleri TEST/BACK, VOL UP, VOL DOWN ve SELECT'tir. TeknoParrot/Windows kurulumunda bu kontrollerin hangi klavye tuşlarına eşlendiği makineye göre değişebilir. Yanlış tahmini sıra servis menüsünde yanlış değeri değiştirebilir.

Bu nedenle örnek:

```json
[
  {"type": "key", "key": "F1", "hold_ms": 100, "wait_ms": 900},
  {"type": "key", "key": "F2", "hold_ms": 100, "wait_ms": 900}
]
```

yalnız biçim örneğidir ve otomatik olarak etkinleştirilmez.

## Kesin sıra nasıl tamamlanır?

1. TeknoParrot Controller Setup'ta TEST/BACK, VOL UP, VOL DOWN ve SELECT karşılıklarını not edin.
2. Oyunda operatör menüsünü elle açın.
3. `Credits Per Play` değerini `4`ten `1`e giderken her tuşu ve beklemeyi sırayla not edin.
4. Manager'daki JSON alanına bu gerçek sırayı yazın.
5. **Doğrula, Kaydet ve Pico'ya Yaz** düğmesini kullanın.
6. Önce **Makroyu Şimdi Çalıştır** ile gözlemleyin.
7. Doğru çalışırsa otomatik makroyu açın.
8. En az 10 soğuk açılışta test edin.

Bu saha ölçümü yapılmadan proje gerçek sırayı dürüstçe bilemez; fakat sırayı çalıştıracak bütün yazılım ve Pico altyapısı tamamdır.
