"""Yerel web sayfası:  python app.py   ->   http://localhost:5000

- RabbitMQ'dan gelen sürüşleri otomatik kaydeder (arka planda alici.py çalışır).
- Sürüşleri listeler, araçtan indirilen CSV'leri yüklemeye izin verir.
- Tek tuşla analizi çalıştırır; metrik tablosunu ve grafikleri gösterir.
"""
import json

from flask import Flask, redirect, render_template, request, send_from_directory, url_for

import alici
import analiz
import ayarlar as A
import sahte_veri
from veri_okuma import tum_suruslar

app = Flask(__name__)
mesaj = {"metin": ""}


@app.route("/")
def ana_sayfa():
    suruslar = [b for _, b in tum_suruslar()]
    ozet_yol = A.SONUCLAR / "ozet.json"
    ozet = json.loads(ozet_yol.read_text(encoding="utf-8")) if ozet_yol.exists() else None
    m, mesaj["metin"] = mesaj["metin"], ""
    return render_template("index.html", suruslar=suruslar, ozet=ozet,
                           alici=alici.durum, mesaj=m)


@app.post("/yukle")
def yukle():
    A.HAM_VERI.mkdir(parents=True, exist_ok=True)
    adet = 0
    for f in request.files.getlist("dosyalar"):
        if f.filename.lower().endswith(".csv"):
            f.save(A.HAM_VERI / f.filename.replace("/", "_").replace("\\", "_"))
            adet += 1
    mesaj["metin"] = f"{adet} dosya yüklendi."
    return redirect(url_for("ana_sayfa"))


@app.post("/analiz")
def analiz_et():
    try:
        analiz.calistir(yazdir=False)
        mesaj["metin"] = "Analiz tamamlandı."
    except Exception as h:
        mesaj["metin"] = f"Analiz yapılamadı: {h}"
    return redirect(url_for("ana_sayfa") + "#sonuc")


@app.post("/sahte")
def sahte():
    if request.form.get("islem") == "sil":
        sahte_veri.sil()
        mesaj["metin"] = "Sahte veriler silindi."
    else:
        sahte_veri.sil()
        mesaj["metin"] = f"{sahte_veri.uret()} sahte sürüş üretildi (yalnızca deneme için)."
    return redirect(url_for("ana_sayfa"))


@app.post("/sil/<ad>")
def sil(ad):
    yol = A.HAM_VERI / ad
    if yol.parent == A.HAM_VERI and yol.exists():
        yol.unlink()
        mesaj["metin"] = f"{ad} silindi."
    return redirect(url_for("ana_sayfa"))


@app.route("/sonuc/<ad>")
def sonuc_dosyasi(ad):
    return send_from_directory(A.SONUCLAR, ad)


@app.route("/ham/<ad>")
def ham_dosya(ad):
    return send_from_directory(A.HAM_VERI, ad, as_attachment=True)


if __name__ == "__main__":
    alici.arka_planda_baslat()
    app.run(host="127.0.0.1", port=5000, debug=False)
