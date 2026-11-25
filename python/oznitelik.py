"""Pencereleme ve öznitelik çıkarma (pencere başına 21 öznitelik)."""
import numpy as np
import pandas as pd

import ayarlar as A

EKSENLER = ["ax", "ay", "az", "gx", "gy", "gz"]

OZNITELIKLER = (
    [f"std_{e}" for e in EKSENLER]            # 6: her eksenin standart sapması
    + [f"ptp_{e}" for e in EKSENLER]          # 6: her eksenin tepeden tepeye farkı (maks - min)
    + ["az_ort", "az_min_sapma", "az_maks_sapma",   # 3: az ortalaması, ortalamadan en büyük düşüş / çıkış
       "az_fark_ort", "gy_fark_ort",          # 2: ardışık örnek farklarının mutlak ortalaması (sarsıntı hızı)
       "ivme_buyukluk_std", "ivme_buyukluk_ptp",   # 2: toplam ivme büyüklüğünün std ve tepeden tepeye farkı
       "az_sifir_gecis",                      # 1: az'nin ortalama etrafında yön değiştirme sayısı
       "az_sira"]                             # 1: en düşük nokta en yüksekten önce mi (+) sonra mı (-)
)
assert len(OZNITELIKLER) == 21


# --- EK-1: Öznitelik çıkarma ---
def pencere_oznitelikleri(p: pd.DataFrame) -> list[float]:
    """30 satırlık bir pencereden 21 öznitelik hesaplar."""
    v = {e: p[e].to_numpy(dtype=float) for e in EKSENLER}
    az = v["az"] * A.AZ_ISARET
    az_ort = az.mean()
    buyukluk = np.sqrt(v["ax"] ** 2 + v["ay"] ** 2 + v["az"] ** 2)
    sapma = az - az_ort
    sifir_gecis = int(np.sum(np.diff(np.sign(sapma)) != 0))
    az_sira = (np.argmax(az) - np.argmin(az)) / len(az)   # çukur: önce düşüş -> pozitif

    return ([v[e].std() for e in EKSENLER]
            + [np.ptp(v[e]) for e in EKSENLER]
            + [az_ort, az.min() - az_ort, az.max() - az_ort,
               np.abs(np.diff(az)).mean(), np.abs(np.diff(v["gy"])).mean(),
               buyukluk.std(), np.ptp(buyukluk),
               sifir_gecis, az_sira])


def pencerele(df: pd.DataFrame, etiket: np.ndarray, bilgi: dict) -> pd.DataFrame:
    """Sürüşü kayan pencerelere böler; her pencereye öznitelik ve sınıf verir."""
    satirlar = []
    for bas in range(0, len(df) - A.PENCERE + 1, A.ADIM):
        p = df.iloc[bas:bas + A.PENCERE]
        e = etiket[bas:bas + A.PENCERE]
        engel = e[e != "normal"]
        sinif = "normal"
        if len(engel) >= A.MIN_ORTUSME:
            degerler, sayilar = np.unique(engel, return_counts=True)
            sinif = degerler[np.argmax(sayilar)]
        satirlar.append([bilgi["run_id"], bilgi["parkur"], bilgi["hiz"], bas, sinif]
                        + pencere_oznitelikleri(p))
    return pd.DataFrame(satirlar, columns=["run_id", "parkur", "hiz", "bas_satir", "sinif"]
                        + OZNITELIKLER)
