"""Rapor için grafikler (PNG, 200 dpi)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ayarlar as A

RENK = {"Eşikleme": "#257de0", "K-NN": "#f47230", "Karar Ağacı": "#00b894"}
SINIF_RENK = {"cukur": "#ec4647", "tumsek": "#6a4ce2"}
SINIF_AD = {"normal": "Normal", "cukur": "Çukur", "tumsek": "Tümsek"}
MURE, IKINCIL = "#191919", "#666666"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": "#bbbbbb", "axes.labelcolor": MURE,
    "xtick.color": IKINCIL, "ytick.color": IKINCIL, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e6e6",
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
})


def _kaydet(fig, ad):
    yol = A.SONUCLAR / ad
    fig.tight_layout()
    fig.savefig(yol, dpi=200)
    plt.close(fig)
    return yol.name


def karmasiklik_matrisleri(matrisler: dict) -> str:
    """matrisler: {algoritma: 3x3 dizi (satır=gerçek, sütun=tahmin)}"""
    fig, eksenler = plt.subplots(1, len(matrisler), figsize=(4 * len(matrisler), 3.8))
    eksenler = np.atleast_1d(eksenler)
    adlar = [SINIF_AD[s] for s in A.SINIFLAR]
    for ax, (alg, m) in zip(eksenler, matrisler.items()):
        ax.imshow(m, cmap="Blues")
        ax.grid(False)
        ax.set_xticks(range(3), adlar); ax.set_yticks(range(3), adlar)
        ax.set_xlabel("Tahmin"); ax.set_ylabel("Gerçek"); ax.set_title(alg, color=MURE)
        esik = m.max() / 2 if m.max() else 1
        for i in range(3):
            for j in range(3):
                ax.text(j, i, int(m[i, j]), ha="center", va="center",
                        color="white" if m[i, j] > esik else MURE)
    return _kaydet(fig, "karmasiklik_matrisi.png")


def metrik_karsilastirma(tum: pd.DataFrame) -> str:
    """tum: algoritma başına tüm hızların birleşik metrikleri."""
    metrikler = [("dogruluk", "Doğruluk"), ("kesinlik", "Kesinlik"),
                 ("duyarlilik", "Duyarlılık"), ("f1", "F1")]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = np.arange(len(metrikler))
    gen = 0.8 / len(tum)
    for i, (_, r) in enumerate(tum.iterrows()):
        ax.bar(x + (i - (len(tum) - 1) / 2) * gen, [r[m] for m, _ in metrikler],
               width=gen - 0.02, color=RENK[r["algoritma"]], label=r["algoritma"])
    ax.set_xticks(x, [ad for _, ad in metrikler])
    ax.set_ylim(0, 1.05); ax.set_ylabel("Değer")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    ax.grid(axis="x", visible=False)
    return _kaydet(fig, "metrik_karsilastirma.png")


def hiza_gore(hiz_tablo: pd.DataFrame) -> list[str]:
    """Hız seviyesine göre F1 ve yanlış alarm sayısı (iki ayrı grafik)."""
    dosyalar = []
    for sutun, baslik, ad in [("f1", "F1 skoru", "hiza_gore_f1.png"),
                              ("FP", "Yanlış alarm sayısı (FP)", "hiza_gore_yanlis_alarm.png")]:
        fig, ax = plt.subplots(figsize=(6, 3.6))
        for alg, g in hiz_tablo.groupby("algoritma", sort=False):
            g = g.sort_values("hiz")
            ax.plot(g["hiz"], g[sutun], marker="o", markersize=7, linewidth=2,
                    color=RENK[alg], label=alg)
        ax.set_xticks(sorted(hiz_tablo["hiz"].unique()))
        ax.set_xlabel("Hız seviyesi"); ax.set_ylabel(baslik)
        if sutun == "f1":
            ax.set_ylim(0, 1.05)
        else:
            ax.set_ylim(bottom=0)
        ax.legend()
        dosyalar.append(_kaydet(fig, ad))
    return dosyalar


def ham_sinyal(df: pd.DataFrame, etiket: np.ndarray, bilgi: dict, esik: float | None) -> str:
    """Bir sürüşün az sinyali; engel bölümleri renkli gölgeli."""
    t = df["t_ms"].to_numpy() / 1000
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(t, df["az"], color=MURE, linewidth=1, label="az")
    for sinif in ("cukur", "tumsek"):
        maske = etiket == sinif
        ax.fill_between(t, 0, 1, where=maske, transform=ax.get_xaxis_transform(),
                        color=SINIF_RENK[sinif], alpha=0.18, label=SINIF_AD[sinif], step="mid")
    ax.set_xlabel("Zaman (s)"); ax.set_ylabel("Dikey ivme az (g)")
    ax.set_title(f"Sürüş {bilgi['run_id']} · hız {bilgi['hiz']}", color=MURE)
    ax.legend(ncol=3, loc="lower right")
    return _kaydet(fig, "ham_sinyal_az.png")


def esik_dagilimi(pencereler: pd.DataFrame, esikler: dict) -> str:
    """Her hızda std(az) değerleri ve hesaplanan eşik."""
    hizlar = sorted(pencereler["hiz"].unique())
    fig, eksenler = plt.subplots(1, len(hizlar), figsize=(4 * len(hizlar), 3.4), sharey=True)
    eksenler = np.atleast_1d(eksenler)
    for ax, h in zip(eksenler, hizlar):
        g = pencereler[pencereler["hiz"] == h]
        for i, s in enumerate(A.SINIFLAR):
            d = g[g["sinif"] == s]["std_az"]
            ax.scatter(np.full(len(d), i) + np.random.uniform(-0.15, 0.15, len(d)), d,
                       s=10, color=SINIF_RENK.get(s, "#888888"), alpha=0.6)
        if h in esikler:
            ax.axhline(esikler[h], color=RENK["Eşikleme"], linewidth=2, linestyle="--")
            ax.text(2.4, esikler[h], f"eşik {esikler[h]:.3f}", va="bottom", ha="right",
                    color=MURE, fontsize=9)
        ax.set_xticks(range(3), [SINIF_AD[s] for s in A.SINIFLAR])
        ax.set_title(f"Hız {h}", color=MURE)
        ax.grid(axis="x", visible=False)
    eksenler[0].set_ylabel("std(az) (g)")
    return _kaydet(fig, "esik_dagilimi.png")
