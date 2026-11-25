# Rapor EK'i için kod parçaları

Tam kod: https://github.com/muratonat91/TURTEP_MURAT_ONAT_BASAR

## EK-1a. ESP32-S3: 100 Hz MPU-6050 okuma görevi
Dosya: `arduino/cukur_arac/cukur_arac.ino`
```cpp
// 100 Hz örnekleme görevi: ayrı çekirdekte, sürüş ve web sayfasından bağımsız çalışır.
void ornekGorevi(void*) {
  TickType_t son = xTaskGetTickCount();
  for (;;) {
    vTaskDelayUntil(&son, pdMS_TO_TICKS(ORNEK_PERIYOT_MS));
    if (!mpuHazir) continue;
    int16_t a[3], g[3];
    if (!mpuOku(a, g)) continue;
    uint8_t m = (digitalRead(PIN_YAN) == YAN_SIYAH_SEVIYE) ? 1 : 0;
    for (int i = 0; i < 3; i++) { sonA[i] = a[i]; sonG[i] = g[i]; }
    sonMarker = m;
    if (kayitta && ornekSayisi < AZAMI_ORNEK) {
      Ornek& o = tampon[ornekSayisi];
      o.t = millis() - kayitBaslangic;
      for (int i = 0; i < 3; i++) { o.a[i] = a[i]; o.g[i] = g[i]; }
      o.marker = m;
      ornekSayisi = ornekSayisi + 1;
    }
  }
}
```

## EK-1b. ESP32-S3: Ölçümlerin MQTT ile paketler halinde gönderilmesi
```cpp
void mqttGonder() {
  if (!mqtt.connected()) return;
  int n = ornekSayisi;
  if (gonderilen < n) {
    // Başlangıç mesajı kaçtıysa (sürüş başında bağlantı yoksa) şimdi gönder
    if (gonderilen == 0) {
      String m = String(runId) + "," + hizSeviyesi + "," + yon + "," + parkur;
      mqtt.publish("cukur/basla", m.c_str());
    }
    int son = min(n, gonderilen + PAKET_SATIR);
    if (suruste && son - gonderilen < PAKET_SATIR) return;  // paket dolana kadar bekle
    String paket;
    paket.reserve(PAKET_SATIR * 64);
    for (int i = gonderilen; i < son; i++) { paket += satir(i); paket += '\n'; }
    if (mqtt.publish("cukur/veri", paket.c_str())) gonderilen = son;
  } else if (!suruste && !bitisMesajiGonderildi && n > 0) {
    String m = String(runId) + "," + n;
    if (mqtt.publish("cukur/bitti", m.c_str())) bitisMesajiGonderildi = true;
  }
}
```

## EK-2. Pencere başına 21 öznitelik çıkarma
Dosya: `python/oznitelik.py`
```python
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
```

## EK-3. Eşikleme (her hız için ayrı eşik)
Dosya: `python/siniflandirici.py`
```python
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
```

## EK-4. K-NN ve Karar Ağacı modelleri
```python
def knn_modeli():
    # Öznitelikler farklı birimlerde olduğu için uzaklık hesabından önce standartlaştırılır.
    return make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=A.KNN_K))


def agac_modeli():
    return DecisionTreeClassifier(max_depth=A.AGAC_DERINLIK, random_state=A.RASTGELE)
```

## EK-5. Sürüş bazında eğitim/test ayrımı
Dosya: `python/analiz.py`
```python
def surus_ayir(run_idler, oran, tohum):
    """Sürüşleri (pencereleri değil) eğitim ve teste ayırır; aynı sürüş iki tarafta yer almaz."""
    run_idler = np.array(sorted(run_idler))
    rng = np.random.default_rng(tohum)
    rng.shuffle(run_idler)
    n_test = min(max(1, round(len(run_idler) * oran)), len(run_idler) - 1)
    return sorted(run_idler[n_test:].tolist()), sorted(run_idler[:n_test].tolist())
```
