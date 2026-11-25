"""Tüm analizi çalıştırır:  python analiz.py

1. veri/ham içindeki sürüşleri okur ve etiketler.
2. 30 satırlık pencerelere böler, 21 öznitelik çıkarır.
3. Boş parkur sürüşlerinden her hız için eşik hesaplar.
4. Engelli sürüşleri her hızda SÜRÜŞ BAZINDA eğitim/test olarak ayırır.
5. Eşikleme, K-NN ve Karar Ağacı'nı aynı test sürüşleri üzerinde ölçer.
6. Tabloları ve grafikleri sonuclar/ klasörüne yazar.
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)

import ayarlar as A
import grafik
from oznitelik import pencerele
from siniflandirici import Esikleme, agac_modeli, knn_modeli, ogren_ve_tahmin
from veri_okuma import satir_etiketleri, tum_suruslar

ALGORITMALAR = ["Eşikleme", "K-NN", "Karar Ağacı"]


def metrikler(gercek, tahmin) -> dict:
    """Üç sınıf için doğruluk ve makro ortalama kesinlik/duyarlılık/F1.
    TP/TN/FP/FN 'engel var mı?' sorusuna göre: pozitif = çukur veya tümsek.
    FP = normal yolda verilen yanlış alarm."""
    gercek, tahmin = np.asarray(gercek), np.asarray(tahmin)
    p, r, f, _ = precision_recall_fscore_support(gercek, tahmin, labels=A.SINIFLAR,
                                                 average="macro", zero_division=0)
    g_eng, t_eng = gercek != "normal", tahmin != "normal"
    TP = int(np.sum(g_eng & t_eng)); TN = int(np.sum(~g_eng & ~t_eng))
    FP = int(np.sum(~g_eng & t_eng)); FN = int(np.sum(g_eng & ~t_eng))
    return {"pencere": len(gercek), "dogruluk": accuracy_score(gercek, tahmin),
            "kesinlik": p, "duyarlilik": r, "f1": f,
            "TP": TP, "TN": TN, "FP": FP, "FN": FN,
            "yanlis_alarm_orani": FP / (FP + TN) if FP + TN else 0.0}


def surus_ayir(run_idler, oran, tohum):
    """Sürüşleri (pencereleri değil) eğitim ve teste ayırır; aynı sürüş iki tarafta yer almaz."""
    run_idler = np.array(sorted(run_idler))
    rng = np.random.default_rng(tohum)
    rng.shuffle(run_idler)
    n_test = min(max(1, round(len(run_idler) * oran)), len(run_idler) - 1)
    return sorted(run_idler[n_test:].tolist()), sorted(run_idler[:n_test].tolist())


def calistir(yazdir=True) -> dict:
    A.SONUCLAR.mkdir(parents=True, exist_ok=True)
    suruslar, parcalar = [], []
    for df, bilgi in tum_suruslar():
        etiket = satir_etiketleri(df, bilgi)
        suruslar.append((df, etiket, bilgi))
        parcalar.append(pencerele(df, etiket, bilgi))
    if not parcalar:
        raise RuntimeError("veri/ham klasöründe sürüş yok.")
    pencereler = pd.concat(parcalar, ignore_index=True)
    pencereler.to_csv(A.SONUCLAR / "pencereler.csv", index=False)

    bos = pencereler[pencereler["parkur"] == "bos"]
    engelli = pencereler[pencereler["parkur"] == "engelli"]
    esikleme = Esikleme().egit(bos)

    satirlar, ayrimlar = [], {}
    tum_gercek = {a: [] for a in ALGORITMALAR}
    tum_tahmin = {a: [] for a in ALGORITMALAR}
    uyarilar = []

    for hiz in sorted(engelli["hiz"].unique()):
        hiz = int(hiz)
        g = engelli[engelli["hiz"] == hiz]
        runlar = g["run_id"].unique()
        if len(runlar) < 2:
            uyarilar.append(f"Hız {hiz}: en az 2 engelli sürüş gerekli, atlandı.")
            continue
        egitim_r, test_r = surus_ayir(runlar, A.TEST_ORANI, A.RASTGELE + hiz)
        ayrimlar[hiz] = {"egitim": egitim_r, "test": test_r}
        egitim = g[g["run_id"].isin(egitim_r)]
        test = g[g["run_id"].isin(test_r)]

        tahminler = {
            "K-NN": ogren_ve_tahmin(knn_modeli(), egitim, test),
            "Karar Ağacı": ogren_ve_tahmin(agac_modeli(), egitim, test),
        }
        if hiz in esikleme.esik:
            tahminler = {"Eşikleme": esikleme.tahmin(test, hiz), **tahminler}
        else:
            uyarilar.append(f"Hız {hiz}: boş parkur sürüşü yok, eşikleme yapılamadı.")

        for alg, tahmin in tahminler.items():
            satirlar.append({"algoritma": alg, "hiz": hiz, **metrikler(test["sinif"], tahmin)})
            tum_gercek[alg] += list(test["sinif"]); tum_tahmin[alg] += list(tahmin)

    hiz_tablo = pd.DataFrame(satirlar)
    tum_tablo = pd.DataFrame([{"algoritma": a, "hiz": "tümü", **metrikler(tum_gercek[a], tum_tahmin[a])}
                              for a in ALGORITMALAR if tum_gercek[a]])
    tablo = pd.concat([hiz_tablo, tum_tablo], ignore_index=True)
    tablo.round(4).to_csv(A.SONUCLAR / "metrikler.csv", index=False)

    grafikler = []
    if not tum_tablo.empty:
        matrisler = {a: confusion_matrix(tum_gercek[a], tum_tahmin[a], labels=A.SINIFLAR)
                     for a in ALGORITMALAR if tum_gercek[a]}
        grafikler.append(grafik.karmasiklik_matrisleri(matrisler))
        grafikler.append(grafik.metrik_karsilastirma(tum_tablo))
        grafikler += grafik.hiza_gore(hiz_tablo)
    ornek = next((s for s in suruslar if s[2]["parkur"] == "engelli"), None)
    if ornek:
        grafikler.append(grafik.ham_sinyal(*ornek, esikleme.esik.get(ornek[2]["hiz"])))
    if esikleme.esik:
        grafikler.append(grafik.esik_dagilimi(pencereler, esikleme.esik))

    ozet = {
        "surus_sayisi": len(suruslar),
        "pencere_sayisi": len(pencereler),
        "sinif_dagilimi": pencereler.groupby(["parkur", "sinif"]).size()
                          .rename("adet").reset_index().to_dict("records"),
        "esikler": {str(k): round(v, 5) for k, v in esikleme.esik.items()},
        "egitim_test_surusleri": {str(k): v for k, v in ayrimlar.items()},
        "uyarilar": uyarilar,
        "grafikler": grafikler,
        "metrikler": tablo.round(4).to_dict("records"),
    }
    (A.SONUCLAR / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    if yazdir:
        pd.set_option("display.width", 160)
        print(tablo.round(3).to_string(index=False))
        print("Eşikler:", ozet["esikler"])
        for u in uyarilar:
            print("Uyarı:", u)
        print("Sonuçlar:", A.SONUCLAR)
    return ozet


if __name__ == "__main__":
    calistir()
