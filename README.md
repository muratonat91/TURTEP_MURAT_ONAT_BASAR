# TURTEP_MURAT_ONAT_BASAR

**İvmeölçer (MPU6050) Verileri Kullanılarak Yol Anormalliklerinin (Çukur/Tümsek) Sınıflandırılmasında Farklı Algoritmaların Başarı Karşılaştırması**

Ahmet Yesevi Üniversitesi, Yazılım Mühendisliği Tezsiz Yüksek Lisans dönem projesinin yazılımlarıdır.

## Sistem nasıl çalışır?

```
 [ESP32-S3 araç]  --Wi-Fi (CUKUR-ARAC)-->  [Bilgisayar]
   MPU-6050, 100 Hz                         RabbitMQ (MQTT eklentisi, port 1883)
   çizgi izleme                                 |  kalıcı kuyruk: cukur_veri
   yan sensör -> marker                         v
   MQTT: cukur/basla, cukur/veri, cukur/bitti   alici.py  -> veri/ham/run_*.csv
                                                analiz.py -> sonuclar/ (tablo + grafik)
                                                app.py    -> http://localhost:5000
```

1. Araç kendi Wi-Fi ağını açar. Bilgisayar ve telefon bu ağa bağlanır.
2. Telefondan `http://192.168.4.1` açılır; parkur tipi, hız ve yön seçilip sürüş başlatılır.
3. Araç ölçümleri MQTT ile bilgisayardaki RabbitMQ'ya gönderir. `app.py` her sürüşü ayrı CSV olarak kaydeder.
4. `http://localhost:5000` sayfasında **ANALİZİ ÇALIŞTIR** düğmesine basılır. Tablolar ve grafikler çıkar.

CSV sütunları: `run_id, t_ms, ax, ay, az, gx, gy, gz, marker, speed_level, direction`
(ivme g, açısal hız °/s; marker=1 aracın engel yanındaki siyah bandın üzerinde olduğunu gösterir).

## Klasörler

| Klasör / dosya | Görevi |
|---|---|
| `arduino/cukur_arac/cukur_arac.ino` | ESP32-S3 araç kodu: çizgi izleme, 100 Hz MPU-6050 okuma, web sayfası, CSV indirme, MQTT gönderimi |
| `python/ayarlar.py` | Tüm ayarlar (pencere boyu, engel sırası, eşik katsayısı, k değeri...) |
| `python/alici.py` | RabbitMQ kuyruğundan veriyi alıp her sürüşü CSV'ye yazar |
| `python/veri_okuma.py` | CSV okuma ve satır etiketleme (marker bölümleri → tümsek, çukur, tümsek) |
| `python/oznitelik.py` | 30 satırlık (0,3 s) pencereler ve 21 öznitelik |
| `python/siniflandirici.py` | Eşikleme, K-NN (k=3) ve Karar Ağacı |
| `python/analiz.py` | Sürüş bazında eğitim/test ayrımı, metrikler, grafikler |
| `python/grafik.py` | Karmaşıklık matrisi, metrik karşılaştırma, hıza göre başarı, ham sinyal, eşik dağılımı |
| `python/app.py` | Yerel web sayfası |
| `python/sahte_veri.py` | Araç olmadan deneme için sahte veri (raporda kullanılmaz) |
| `docs/EK_kod_parcalari.md` | Rapor ekine konacak kısa kod parçaları |

---

## Kurulum (Windows)

### 1. Araç kodu (Arduino IDE)

1. [Arduino IDE 2](https://www.arduino.cc/en/software) kurun.
2. *Dosya > Tercihler > Ek kart yöneticisi adresleri* kısmına ekleyin:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. *Araçlar > Kart > Kart Yöneticisi*: **esp32 by Espressif Systems** kurun.
4. *Araçlar > Kütüphaneleri Yönet*: **PubSubClient** (Nick O'Leary) kurun.
5. `arduino/cukur_arac/cukur_arac.ino` dosyasını açın.
6. Dosyanın başındaki **AYARLAR** bölümünde pin numaralarını kendi bağlantınıza göre düzeltin
   (L298N IN1-IN4, ENA, ENB; çizgi sensörleri; yan sensör; MPU-6050 SDA/SCL).
   - L298N üzerindeki ENA/ENB jumper'larını çıkarın ve bu pinleri ESP32'ye bağlayın, yoksa hız ayarı çalışmaz.
   - Sensör siyahta LOW veriyorsa `CIZGI_SIYAH_SEVIYE` / `YAN_SIYAH_SEVIYE` değerini `LOW` yapın.
7. Kart olarak **ESP32S3 Dev Module** seçin, portu seçip yükleyin.
8. Seri monitörde (115200) `MPU-6050 hazir` yazısını görün.

**İlk deneme:** Telefonla `CUKUR-ARAC` ağına bağlanın (şifre `12345678`), `http://192.168.4.1` açın.
- *Motor testi* düğmeleri yanlış tekerleği veya ters yönü döndürürse `SOL_MOTOR_TERS` / `SAG_MOTOR_TERS` değiştirin ya da pinleri yer değiştirin.
- Sayfadaki `cizgi` alanı sensörler siyah çizgi üzerindeyken `1` göstermelidir.
- Araç yan bandın üzerindeyken `yan_sensor` = 1 olmalıdır.
- Araç zikzak çizerse `KP` değerini düşürün, virajda çizgiyi kaçırırsa artırın.

### 2. RabbitMQ (MQTT eklentisiyle)

1. Önce [Erlang](https://www.erlang.org/downloads), sonra [RabbitMQ](https://www.rabbitmq.com/docs/install-windows) kurun.
2. Başlat menüsünden **RabbitMQ Command Prompt (sbin dir)** açın ve sırayla çalıştırın:
   ```
   rabbitmq-plugins enable rabbitmq_mqtt rabbitmq_management
   rabbitmqctl add_user arac arac1234
   rabbitmqctl set_permissions -p / arac ".*" ".*" ".*"
   ```
   (`guest` kullanıcısı yalnızca bilgisayarın kendisinden bağlanabildiği için araç için ayrı kullanıcı açılır.)
3. Yönetici olarak açılmış komut isteminde güvenlik duvarında MQTT portunu açın:
   ```
   netsh advfirewall firewall add rule name="MQTT 1883" dir=in action=allow protocol=TCP localport=1883
   ```
4. Kontrol: tarayıcıda `http://localhost:15672` (guest / guest) açılıyorsa RabbitMQ çalışıyordur.

### 3. Python

```
cd python
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Tarayıcıda `http://localhost:5000` açın. "Veri alıcı: Bağlı" yazısı görülmelidir.

---

## Deney günü

1. RabbitMQ açık olsun, `python app.py` çalıştırın.
2. Bilgisayarı **CUKUR-ARAC** Wi-Fi ağına bağlayın (bu sırada internet olmaz, sorun değil).
3. Bilgisayardan `http://192.168.4.1` açıp **Bu cihaz veri alıcısıdır** düğmesine bir kez basın.
   Sayfada `mqtt: bagli` görünmelidir.
4. Sürüşler:
   - **Boş parkur** (engeller çıkarılmış): her hızda 3 sürüş → eşik hesabı için.
   - **Engelli parkur**: her hızda 10 sürüş.
5. Her sürüşte parkur tipi, hız ve yönü seçip **SÜRÜŞÜ BAŞLAT**. Araç çizgi bitince, bitiş bandını görünce ya da 20 saniye dolunca kendisi durur.
6. `http://localhost:5000` sayfasında sürüşlerin listelendiğini kontrol edin. Engelli sürüşlerde *Marker bölümü* 3 olmalıdır (kırmızıysa o sürüşü silip tekrarlayın).
7. **ANALİZİ ÇALIŞTIR**. Sonuçlar `python/sonuclar/` klasörüne de yazılır (rapora konacak PNG'ler buradadır).

**Yedek yol:** MQTT çalışmazsa her sürüşten sonra araç sayfasındaki **Son sürüşü CSV indir** ile dosyayı alın ve `localhost:5000` sayfasından yükleyin. Dosya adını değiştirmeyin (parkur tipi adın içindedir).

## Analiz yöntemi (kısaca)

- **Etiketleme:** Yan sensörün marker=1 verdiği bölümler sırayla `ENGEL_SIRASI` ile eşlenir (varsayılan: tümsek, çukur, tümsek; B→A yönünde ters). Sarsıntı bandın biraz ardından da sürdüğü için bölüm sonuna `ENGEL_SONRA_PAY` satır eklenir. Gerçek veride `ham_sinyal_az.png` grafiğine bakılarak bu değer ayarlanabilir.
- **Pencere:** 30 satır (0,3 s), %50 örtüşmeli. Pencere bir engel bölümüyle en az 5 satır örtüşürse o engelin sınıfını alır.
- **21 öznitelik:** 6 eksenin standart sapması ve tepeden tepeye farkı (12), az ortalaması ve ortalamadan en büyük düşüş/çıkış (3), az ve gy ardışık fark ortalaması (2), toplam ivme büyüklüğünün std ve tepeden tepeye farkı (2), az sıfır geçiş sayısı (1), az'nin önce düşüp düşmediği (1).
- **Eşikleme:** Her hız için boş parkur pencerelerinin std(az) değerlerinden `eşik = ortalama + 3 × standart sapma`. Eşiği aşan pencerede az önce düştüyse çukur, önce arttıysa tümsek denir.
- **K-NN:** k=3, öznitelikler standartlaştırılır. **Karar Ağacı:** scikit-learn varsayılanları.
- **Eğitim/test:** Her hızda engelli sürüşlerin %30'u test için ayrılır. Ayrım pencere değil sürüş bazındadır; aynı sürüşün parçaları hem eğitimde hem testte bulunmaz. Üç algoritma aynı test sürüşlerinde ölçülür.
- **Metrikler:** Doğruluk; üç sınıfın makro ortalama kesinlik, duyarlılık ve F1 değeri; "engel var mı?" sorusuna göre TP, TN, FP, FN (FP = yanlış alarm) ve yanlış alarm oranı = FP / (FP + TN). Her hız için ayrı ve tüm hızlar için birlikte.

## Araç olmadan deneme

`localhost:5000` sayfasında **Sahte veri üret** düğmesi 39 sahte sürüş üretir (dosya adları `_SAHTE` ile biter). Analiz bu verilerle de çalışır. Gerçek deneylerden önce **Sahte verileri sil** ile temizleyin. Sahte veriler raporda kullanılmamalıdır.

## GitHub Desktop ile yükleme

1. GitHub Desktop: *File > Add local repository* ile bu klasörü seçin. "Not a git repository" uyarısında *create a repository* deyin.
2. Ad: `TURTEP_MURAT_ONAT_BASAR`. *Create repository*.
3. *Publish repository* → **Keep this code private** kutusunun işaretini kaldırın (herkese açık) → *Publish*.
4. Adres: `https://github.com/muratonat91/TURTEP_MURAT_ONAT_BASAR`
