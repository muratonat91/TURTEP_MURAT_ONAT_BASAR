"""Araç olmadan sistemi denemek için SAHTE sürüş verisi üretir.
Bu veriler raporda KULLANILMAZ; sadece yazılımın çalıştığını göstermek içindir.

    python sahte_veri.py            # her hızda 3 boş + 10 engelli sürüş
    python sahte_veri.py --sil      # önce veri/ham içindeki sahte dosyaları siler
"""
import argparse

import numpy as np
import pandas as pd

import ayarlar as A

HZ = 100
PARKUR_M = 1.0
ENGEL_KONUM = [0.30, 0.50, 0.70]     # m
BANT_M = 0.04                        # yan bandın genişliği
HIZ_MS = {1: 0.15, 2: 0.22, 3: 0.30}  # yaklaşık araç hızı (m/s)


def tepki(n, hiz, isaret, rng):
    """Engel geçişindeki sönümlü salınım. Tümsekte önce yukarı (+), çukurda önce aşağı (-)."""
    t = np.arange(n) / HZ
    genlik = (0.25 + 0.25 * hiz) * rng.uniform(0.8, 1.2)
    return isaret * genlik * np.exp(-t * 18) * np.sin(2 * np.pi * 9 * t)


def surus(run_id, hiz, parkur, yon, rng):
    v = HIZ_MS[hiz] * rng.uniform(0.93, 1.07)
    n = int(PARKUR_M / v * HZ)
    t = np.arange(n) / HZ
    gurultu = 0.02 + 0.015 * hiz
    ax = rng.normal(0, gurultu, n); ay = rng.normal(0, gurultu, n)
    az = 1.0 + rng.normal(0, gurultu, n)
    g = [rng.normal(0, 0.8 + 0.5 * hiz, n) for _ in range(3)]
    marker = np.zeros(n, dtype=int)

    # normal yolda ara sıra küçük sarsıntılar (yanlış alarm kaynağı)
    for _ in range(rng.integers(1, 4)):
        i = rng.integers(0, n - 30)
        az[i:i + 30] += tepki(30, hiz, rng.choice([-1, 1]), rng) * 0.35

    if parkur == "engelli":
        sira = A.ENGEL_SIRASI[::-1] if yon == 1 else A.ENGEL_SIRASI
        for konum, sinif in zip(ENGEL_KONUM, sira):
            bas = int(konum / v * HZ)
            bant = max(2, int(BANT_M / v * HZ))
            marker[bas:bas + bant] = 1
            isaret = 1 if sinif == "tumsek" else -1
            k = min(40, n - bas)
            az[bas:bas + k] += tepki(k, hiz, isaret, rng)
            g[1][bas:bas + k] += tepki(k, hiz, isaret, rng) * 40   # gy: öne/arkaya yatma
            ax[bas:bas + k] += tepki(k, hiz, isaret, rng) * 0.3

    return pd.DataFrame({
        "run_id": run_id, "t_ms": (t * 1000).astype(int),
        "ax": ax.round(4), "ay": ay.round(4), "az": az.round(4),
        "gx": g[0].round(2), "gy": g[1].round(2), "gz": g[2].round(2),
        "marker": marker, "speed_level": hiz, "direction": yon,
    })


def uret(bos_adet=3, engelli_adet=10, tohum=1):
    rng = np.random.default_rng(tohum)
    A.HAM_VERI.mkdir(parents=True, exist_ok=True)
    run_id = 9000   # gerçek sürüşlerle karışmasın diye 9000'den başlar
    for hiz in (1, 2, 3):
        for parkur, adet in (("bos", bos_adet), ("engelli", engelli_adet)):
            for i in range(adet):
                run_id += 1
                yon = i % 2
                df = surus(run_id, hiz, parkur, yon, rng)
                df.to_csv(A.HAM_VERI / f"run_{run_id}_{parkur}_h{hiz}_y{yon}_SAHTE.csv", index=False)
    return run_id - 9000


def sil():
    for f in A.HAM_VERI.glob("*_SAHTE.csv"):
        f.unlink()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sil", action="store_true")
    a = ap.parse_args()
    sil()
    if not a.sil:
        print(uret(), "sahte sürüş üretildi:", A.HAM_VERI)
