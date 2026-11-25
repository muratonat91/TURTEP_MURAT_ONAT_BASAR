"""RabbitMQ'dan gelen araç verisini her sürüş için ayrı CSV olarak kaydeder.

Araç MQTT ile yayınlar; RabbitMQ'nun MQTT eklentisi bu mesajları 'amq.topic'
değişimine (exchange) 'cukur.basla', 'cukur.veri', 'cukur.bitti' anahtarlarıyla koyar.
Bu program kalıcı (durable) bir kuyruk açar. Program kapalıyken gelen mesajlar
kuyrukta bekler ve program açılınca kaybolmadan işlenir.

    python alici.py      (tek başına)   veya   python app.py  (web sayfasıyla birlikte)
"""
import threading
import time
from pathlib import Path

import pika

import ayarlar as A

KUYRUK = "cukur_veri"
BASLIK = ",".join(A.SUTUNLAR) + "\n"

durum = {"bagli": False, "son_mesaj": None, "son_run": None, "hata": ""}
_dosyalar: dict[int, str] = {}


def _dosya_adi(run_id, hiz=None, yon=None, parkur=None):
    if parkur is None:
        return A.HAM_VERI / f"run_{run_id}_bilinmiyor.csv"
    return A.HAM_VERI / f"run_{run_id}_{parkur}_h{hiz}_y{yon}.csv"


def mesaj_isle(anahtar: str, govde: str):
    A.HAM_VERI.mkdir(parents=True, exist_ok=True)
    durum["son_mesaj"] = time.strftime("%H:%M:%S")
    if anahtar.endswith("basla"):
        run_id, hiz, yon, parkur = govde.strip().split(",")
        yol = _dosya_adi(int(run_id), hiz, yon, parkur)
        yol.write_text(BASLIK, encoding="utf-8")
        _dosyalar[int(run_id)] = str(yol)
        durum["son_run"] = f"{yol.name} (alınıyor)"
    elif anahtar.endswith("veri"):
        satirlar = [s for s in govde.splitlines() if s.strip()]
        if not satirlar:
            return
        run_id = int(satirlar[0].split(",")[0])
        if run_id not in _dosyalar:
            yol = _dosya_adi(run_id)
            if not yol.exists():
                yol.write_text(BASLIK, encoding="utf-8")
            _dosyalar[run_id] = str(yol)
        with open(_dosyalar[run_id], "a", encoding="utf-8") as f:
            f.write("\n".join(satirlar) + "\n")
    elif anahtar.endswith("bitti"):
        run_id, adet = (int(x) for x in govde.strip().split(","))
        yol = _dosyalar.get(run_id)
        if yol:
            gelen = sum(1 for _ in open(yol, encoding="utf-8")) - 1
            not_ = "tamam" if gelen == adet else f"EKSİK: {gelen}/{adet}"
            durum["son_run"] = f"{Path(yol).name} ({not_})"
            print(f"Sürüş {run_id} kaydedildi: {gelen} satır ({not_})")


def calistir(sunucu="localhost"):
    """Bağlantı koparsa 5 saniyede bir yeniden dener."""
    while True:
        try:
            baglanti = pika.BlockingConnection(pika.ConnectionParameters(host=sunucu))
            kanal = baglanti.channel()
            kanal.queue_declare(queue=KUYRUK, durable=True)
            kanal.queue_bind(queue=KUYRUK, exchange="amq.topic", routing_key="cukur.#")
            durum.update(bagli=True, hata="")
            print("RabbitMQ'ya bağlanıldı, veri bekleniyor...")

            def geri_cagir(ch, yontem, ozellik, govde):
                try:
                    mesaj_isle(yontem.routing_key, govde.decode("utf-8"))
                except Exception as h:
                    print("Mesaj işlenemedi:", h)
                ch.basic_ack(delivery_tag=yontem.delivery_tag)

            kanal.basic_consume(queue=KUYRUK, on_message_callback=geri_cagir)
            kanal.start_consuming()
        except Exception as h:
            durum.update(bagli=False, hata=str(h) or type(h).__name__)
            time.sleep(5)


def arka_planda_baslat():
    threading.Thread(target=calistir, daemon=True).start()


if __name__ == "__main__":
    calistir()
