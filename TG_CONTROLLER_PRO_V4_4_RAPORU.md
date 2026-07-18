# TG_CONTROLLER_PRO V4.4 — Rakam Makrosu Düzeltme Raporu

## Kesin düzeltme

Önceki sürümde sabit makro rakamları yanlış biçimde F1, F2 ve Aşağı tuşlarına
çevriliyordu. Bu eşleştirme tamamen kaldırıldı.

Sabit makro:

```text
345455535455535455335555555544
```

Artık gerçek klavye rakamlarını yazar:

```text
3 → Klavye 3
4 → Klavye 4
5 → Klavye 5
```

Fiziksel Controller pin eşlemesi:

```text
GP4 → Klavye 3
GP5 → Klavye 4
GP6 → Klavye 5
```

## Korunan çalışma sırası

```text
Controller açılır
→ GP3–GP8 ve titreşim röleleri kilitli kalır
→ Ayarlanan 0–999 saniye beklenir
→ 345455535455535455335555555544 rakam makrosu çalışır
→ Makro tamamlanınca GP2 kredisi beklenir
→ GP2 kısa basışla kredi gönderilir
→ Oyun butonları kullanılabilir olur
```

GP9 kısa basışta bekleme süresini atlayarak aynı sabit rakam makrosunu hemen
çalıştırır.

## Önemli

Bu düzeltme Controller firmware'indedir. Controller Pico'ya V4.4 UF2
yüklenmesi zorunludur. P1 ve P2 Gun firmware'i değişmemiştir.
