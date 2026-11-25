"""Sürüş CSV dosyalarını okur ve her satıra sınıf etiketi verir."""
import re
from pathlib import Path

import numpy as np
import pandas as pd

import ayarlar as A

AD_KALIBI = re.compile(r"run_(\d+)_(bos|engelli)_h(\d)", re.I)


def surus_bilgisi(yol: Path, df: pd.DataFrame) -> dict:
    """Parkur tipini dosya adından okur; adda yoksa marker'a bakar (hiç marker yoksa boş parkur)."""
    m = AD_KALIBI.search(yol.name)
    if m:
        parkur = m.group(2).lower()
    else:
        parkur = "engelli" if df["marker"].sum() > 0 else "bos"
    return {
        "dosya": yol.name,
        "run_id": int(df["run_id"].iloc[0]),
        "parkur": parkur,
        "hiz": int(df["speed_level"].iloc[0]),
        "yon": int(df["direction"].iloc[0]),
        "satir": len(df),
        "marker_bolum": len(marker_bolumleri(df["marker"].to_numpy())),
    }


def surus_oku(yol: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(yol)
    eksik = [s for s in A.SUTUNLAR if s not in df.columns]
    if eksik:
        raise ValueError(f"{yol.name}: eksik sütun {eksik}")
    df = df.sort_values("t_ms").reset_index(drop=True)
    return df, surus_bilgisi(yol, df)


def tum_suruslar(klasor: Path = A.HAM_VERI):
    for yol in sorted(Path(klasor).glob("*.csv")):
        try:
            yield surus_oku(yol)
        except Exception as h:  # bozuk dosya analizi durdurmasın
            print("Atlandı:", h)


def marker_bolumleri(marker: np.ndarray) -> list[tuple[int, int]]:
    """marker=1 olan ardışık satırları [başlangıç, bitiş) bölümleri olarak döndürür.
    Arada kısa boşluk varsa (sensör titremesi) iki bölüm birleştirilir."""
    bolumler, bas = [], None
    for i, m in enumerate(marker):
        if m and bas is None:
            bas = i
        elif not m and bas is not None:
            bolumler.append([bas, i]); bas = None
    if bas is not None:
        bolumler.append([bas, len(marker)])
    birlesik = []
    for b in bolumler:
        if birlesik and b[0] - birlesik[-1][1] < A.MARKER_BOSLUK:
            birlesik[-1][1] = b[1]
        else:
            birlesik.append(b)
    return [tuple(b) for b in birlesik if b[1] - b[0] >= 2]


def satir_etiketleri(df: pd.DataFrame, bilgi: dict) -> np.ndarray:
    """Her satıra 'normal', 'cukur' veya 'tumsek' etiketi verir.
    Bölümler, parkurdaki sabit engel sırasına göre eşlenir."""
    etiket = np.array(["normal"] * len(df), dtype=object)
    if bilgi["parkur"] == "bos":
        return etiket
    sira = A.ENGEL_SIRASI[::-1] if bilgi["yon"] == 1 else A.ENGEL_SIRASI
    bolumler = marker_bolumleri(df["marker"].to_numpy())
    if len(bolumler) != len(sira):
        print(f"Uyarı: run {bilgi['run_id']} içinde {len(bolumler)} marker bölümü var, "
              f"{len(sira)} bekleniyordu. İlk {min(len(bolumler), len(sira))} bölüm kullanıldı.")
    for (bas, bit), sinif in zip(bolumler, sira):
        etiket[bas:min(len(df), bit + A.ENGEL_SONRA_PAY)] = sinif
    return etiket
