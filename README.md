# TG_CONTROLLER_PRO V4.4

## Sabit rakam makrosu

```text
345455535455535455335555555544
```

Doğru eşleştirme:

```text
3 = Klavye 3
4 = Klavye 4
5 = Klavye 5
```

Fiziksel Controller eşlemesi:

```text
GP4 = 3
GP5 = 4
GP6 = 5
```

F1, F2 ve Aşağı tuşları unutulmuştur ve sabit makroda kullanılmaz.

## Çalışma

- Açılışta GP3–GP8 ve titreşim röleleri kilitli kalır.
- Ayarlanan 0–999 saniye sonunda sabit makro çalışır.
- Makro bitince sistem GP2 kredisi bekler.
- GP2 kısa basıştan sonra oyun butonları açılır.
- GP9 makroyu süre beklemeden hemen çalıştırır.
- F8, GP19, kalibrasyon, ortak kredi, titreme filtresi ve 2 dakika röle
  uykusu korunmuştur.

Ayrıntı: `TG_CONTROLLER_PRO_V4_4_RAPORU.md`
