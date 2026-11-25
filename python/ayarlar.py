"""Tüm ayarlar tek yerde. Değiştirmek için sadece bu dosyayı düzenleyin."""
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
HAM_VERI = KLASOR / "veri" / "ham"          # her sürüş bir CSV
SONUCLAR = KLASOR / "sonuclar"              # tablolar ve grafikler

SUTUNLAR = ["run_id", "t_ms", "ax", "ay", "az", "gx", "gy", "gz",
            "marker", "speed_level", "direction"]

# ---- Parkur ----
# Araç A->B yönünde giderken engellerin sırası (yan banttaki marker bölümleri bu sırayla eşlenir).
# B->A yönünde (direction=1) sıra otomatik olarak ters çevrilir.
ENGEL_SIRASI = ["tumsek", "cukur", "tumsek"]
SINIFLAR = ["normal", "cukur", "tumsek"]

# ---- Pencereleme ----
PENCERE = 30            # 30 örnek = 0,3 s (100 Hz)
ADIM = 15               # pencereler arası kayma (15 = %50 örtüşme)
MIN_ORTUSME = 5         # pencere, engel bölümüyle en az bu kadar satır örtüşürse o engelin sınıfını alır
ENGEL_SONRA_PAY = 10    # sarsıntı bandın biraz ardından da sürdüğü için bölüm sonuna eklenen satır
MARKER_BOSLUK = 5       # aradaki boşluk bu kadar satırdan kısaysa iki marker bölümü birleştirilir

# ---- Eşikleme ----
ESIK_K = 3.0            # eşik = boş parkur std(az) ortalaması + K * standart sapması
AZ_ISARET = 1           # sensör ters takılıysa -1 yapın (çukurda az önce düşer, tümsekte önce artar)

# ---- Makine öğrenmesi ----
KNN_K = 3
AGAC_DERINLIK = None    # None = sınırsız; aşırı öğrenme görülürse ör. 5 yapın
TEST_ORANI = 0.3        # engelli sürüşlerin test için ayrılan oranı (sürüş bazında)
RASTGELE = 42
