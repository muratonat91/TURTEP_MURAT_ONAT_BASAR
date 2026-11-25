"""Karşılaştırılan üç algoritma: Eşikleme, K-NN ve Karar Ağacı."""
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

import ayarlar as A
from oznitelik import OZNITELIKLER


# --- EK-2: Eşikleme ---
class Esikleme:
    """Boş parkur pencerelerinden her hız için ayrı eşik hesaplar.
    std(az) eşiği aşan pencere engel sayılır; az'nin önce düşmesi çukur, önce artması tümsektir."""

    def __init__(self, k: float = A.ESIK_K):
        self.k = k
        self.esik = {}

    def egit(self, bos_pencereler: pd.DataFrame):
        for hiz, grup in bos_pencereler.groupby("hiz"):
            s = grup["std_az"]
            self.esik[int(hiz)] = float(s.mean() + self.k * s.std())
        return self

    def tahmin(self, X: pd.DataFrame, hiz: int) -> np.ndarray:
        esik = self.esik[hiz]
        return np.where(X["std_az"] <= esik, "normal",
                        np.where(X["az_sira"] > 0, "cukur", "tumsek"))


# --- EK-3: K-NN ve Karar Ağacı ---
def knn_modeli():
    # Öznitelikler farklı birimlerde olduğu için uzaklık hesabından önce standartlaştırılır.
    return make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=A.KNN_K))


def agac_modeli():
    return DecisionTreeClassifier(max_depth=A.AGAC_DERINLIK, random_state=A.RASTGELE)


def ogren_ve_tahmin(model, egitim: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    model.fit(egitim[OZNITELIKLER], egitim["sinif"])
    return model.predict(test[OZNITELIKLER])
