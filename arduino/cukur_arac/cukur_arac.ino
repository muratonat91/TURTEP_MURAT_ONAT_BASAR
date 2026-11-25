/*
  ÇUKUR / TÜMSEK VERİ TOPLAMA ARACI  (ESP32-S3 + MPU-6050 + L298N)
  -----------------------------------------------------------------
  Ne yapar?
    - Önteki kızılötesi sensörlerle siyah çizgiyi izler.
    - MPU-6050'yi saniyede 100 kez (100 Hz) okur.
    - Yandaki HW-096 sensörü engelin yanındaki siyah bandı görünce marker=1 yazar.
    - Kendi Wi-Fi ağını açar: CUKUR-ARAC  (adres: http://192.168.4.1)
    - Web sayfasından: hız (1/2/3), yön, parkur tipi, sürüş başlat/durdur, CSV indir.
    - Ölçümleri MQTT ile bilgisayardaki RabbitMQ'ya paketler halinde gönderir.

  CSV sütunları:
    run_id,t_ms,ax,ay,az,gx,gy,gz,marker,speed_level,direction
    (ivme: g, açısal hız: derece/s)

  Gerekli kütüphane (Arduino IDE > Kütüphane Yöneticisi):
    - PubSubClient (Nick O'Leary)
  Kart: "ESP32S3 Dev Module" (esp32 by Espressif Systems, 2.x veya 3.x)

  >>> PİN NUMARALARINI AŞAĞIDAKİ "AYARLAR" BÖLÜMÜNDEN KENDİ BAĞLANTINIZA GÖRE DEĞİŞTİRİN <<<
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Preferences.h>
#include <PubSubClient.h>

// =====================================================================
//                              AYARLAR
// =====================================================================

// ---- MPU-6050 (I2C) ----
const int PIN_SDA = 8;
const int PIN_SCL = 9;
const uint8_t MPU_ADRES = 0x68;      // AD0 pini 3.3V'a bağlıysa 0x69 yapın

// ---- L298N motor sürücü ----
// Not: ENA/ENB üzerindeki jumper'lar çıkarılmalı, yoksa hız ayarı çalışmaz.
const int PIN_ENA = 4;   // sol motor hız (PWM)
const int PIN_IN1 = 5;   // sol motor yön
const int PIN_IN2 = 6;
const int PIN_ENB = 7;   // sağ motor hız (PWM)
const int PIN_IN3 = 15;  // sağ motor yön
const int PIN_IN4 = 16;
const bool SOL_MOTOR_TERS = false;   // motor ters dönüyorsa true yapın
const bool SAG_MOTOR_TERS = false;

// ---- Çizgi izleme sensörleri (soldan sağa) ----
const int CIZGI_SAYISI = 4;
const int PIN_CIZGI[CIZGI_SAYISI] = {10, 11, 12, 13};
const int CIZGI_SIYAH_SEVIYE = HIGH;   // sensör siyahı görünce verdiği seviye (çoğu modülde HIGH)

// ---- Yan sensör (engel yanındaki siyah bant -> marker) ----
const int PIN_YAN = 14;
const int YAN_SIYAH_SEVIYE = HIGH;

// ---- Hız seviyeleri (PWM 0-255) ----
const int HIZ_PWM[4] = {0, 140, 180, 220};   // [0] kullanılmaz; 1, 2, 3 hız seviyeleri
const float KP = 45.0;                       // çizgi izleme düzeltme katsayısı

// ---- Sürüşün kendiliğinden bitmesi ----
const uint32_t AZAMI_SURE_MS   = 20000;  // en uzun sürüş süresi
const uint32_t CIZGI_KAYIP_MS  = 700;    // çizgi bu kadar süre görünmezse durur
const bool     BITIS_CIZGISI   = true;   // tüm sensörler siyah görürse (bitiş bandı) durur
const uint32_t BITIS_SURE_MS   = 80;

// ---- Wi-Fi erişim noktası ----
const char* AP_ADI   = "CUKUR-ARAC";
const char* AP_SIFRE = "12345678";       // en az 8 karakter

// ---- MQTT (RabbitMQ) ----
const char* VARSAYILAN_BROKER = "192.168.4.2";   // web sayfasından değiştirilebilir
const uint16_t MQTT_PORT  = 1883;
const char* MQTT_KULLANICI = "arac";
const char* MQTT_SIFRE     = "arac1234";
const int   PAKET_SATIR    = 25;               // bir MQTT mesajındaki satır sayısı

// ---- Kayıt ----
const uint32_t ORNEK_PERIYOT_MS = 10;          // 10 ms = 100 Hz
const int AZAMI_ORNEK = 4000;                  // 40 saniyelik bellek

// =====================================================================

struct Ornek {
  uint32_t t;
  int16_t a[3];
  int16_t g[3];
  uint8_t marker;
};

WebServer sunucu(80);
WiFiClient wifiIstemci;
PubSubClient mqtt(wifiIstemci);
Preferences tercihler;

Ornek* tampon = nullptr;
volatile int ornekSayisi = 0;
volatile bool kayitta = false;
volatile uint32_t kayitBaslangic = 0;
volatile int16_t sonA[3] = {0, 0, 0}, sonG[3] = {0, 0, 0};
volatile uint8_t sonMarker = 0;
bool mpuHazir = false;

bool suruste = false;
int runId = 0;
int hizSeviyesi = 1;
int yon = 0;                 // 0: A->B, 1: B->A (yalnızca etiket olarak kaydedilir)
String parkur = "engelli";   // "bos" veya "engelli"
String brokerIp;
int gonderilen = 0;
bool bitisMesajiGonderildi = true;
String durmaNedeni = "";

float sonHata = 0;
uint32_t sonCizgiGorulme = 0;
uint32_t bitisBasladi = 0;
uint32_t sonMqttDeneme = 0;

// ------------------------- MPU-6050 -------------------------
void mpuYaz(uint8_t reg, uint8_t deger) {
  Wire.beginTransmission(MPU_ADRES);
  Wire.write(reg);
  Wire.write(deger);
  Wire.endTransmission();
}

bool mpuBaslat() {
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  Wire.beginTransmission(MPU_ADRES);
  if (Wire.endTransmission() != 0) return false;
  mpuYaz(0x6B, 0x00);  // uyku modundan çıkar
  mpuYaz(0x19, 0x00);  // örnekleme bölücü
  mpuYaz(0x1A, 0x03);  // dijital alçak geçiren filtre ~44 Hz
  mpuYaz(0x1B, 0x00);  // jiroskop ±250 °/s  (131 LSB/°/s)
  mpuYaz(0x1C, 0x00);  // ivmeölçer ±2 g     (16384 LSB/g)
  return true;
}

bool mpuOku(int16_t a[3], int16_t g[3]) {
  Wire.beginTransmission(MPU_ADRES);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADRES, 14) != 14) return false;
  uint8_t b[14];
  for (int i = 0; i < 14; i++) b[i] = Wire.read();
  for (int i = 0; i < 3; i++) a[i] = (int16_t)((b[2 * i] << 8) | b[2 * i + 1]);
  for (int i = 0; i < 3; i++) g[i] = (int16_t)((b[8 + 2 * i] << 8) | b[9 + 2 * i]);
  return true;
}

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

// ------------------------- Motorlar -------------------------
void tekMotor(int en, int i1, int i2, int hiz, bool ters) {
  if (ters) hiz = -hiz;
  hiz = constrain(hiz, -255, 255);
  digitalWrite(i1, hiz > 0 ? HIGH : LOW);
  digitalWrite(i2, hiz < 0 ? HIGH : LOW);
  analogWrite(en, abs(hiz));
}

void motorSur(int sol, int sag) {
  tekMotor(PIN_ENA, PIN_IN1, PIN_IN2, sol, SOL_MOTOR_TERS);
  tekMotor(PIN_ENB, PIN_IN3, PIN_IN4, sag, SAG_MOTOR_TERS);
}

void motorDur() { motorSur(0, 0); }

// ------------------------- Çizgi izleme -------------------------
int cizgiOku(bool s[CIZGI_SAYISI]) {
  int adet = 0;
  for (int i = 0; i < CIZGI_SAYISI; i++) {
    s[i] = digitalRead(PIN_CIZGI[i]) == CIZGI_SIYAH_SEVIYE;
    if (s[i]) adet++;
  }
  return adet;
}

void cizgiIzle() {
  bool s[CIZGI_SAYISI];
  int adet = cizgiOku(s);
  uint32_t simdi = millis();
  int taban = HIZ_PWM[hizSeviyesi];

  if (BITIS_CIZGISI && adet == CIZGI_SAYISI) {
    if (bitisBasladi == 0) bitisBasladi = simdi;
    if (simdi - bitisBasladi > BITIS_SURE_MS) { surusuBitir("bitis cizgisi"); return; }
  } else {
    bitisBasladi = 0;
  }

  float hata;
  if (adet == 0) {
    if (simdi - sonCizgiGorulme > CIZGI_KAYIP_MS) { surusuBitir("cizgi kayboldu"); return; }
    hata = (sonHata < 0) ? -3 : 3;            // çizgi en son hangi taraftaysa o yöne dön
  } else {
    sonCizgiGorulme = simdi;
    float toplam = 0;
    for (int i = 0; i < CIZGI_SAYISI; i++) {
      float agirlik = (2.0 * i - (CIZGI_SAYISI - 1));  // 4 sensör: -3, -1, 1, 3
      if (s[i]) toplam += agirlik;
    }
    hata = toplam / adet;
    sonHata = hata;
  }
  int duzeltme = (int)(KP * hata);
  motorSur(taban + duzeltme, taban - duzeltme);
}

// ------------------------- Sürüş -------------------------
void surusuBaslat(int hiz, int y, const String& p) {
  if (suruste) return;
  hizSeviyesi = constrain(hiz, 1, 3);
  yon = (y == 1) ? 1 : 0;
  parkur = (p == "bos") ? "bos" : "engelli";
  runId++;
  tercihler.putInt("runId", runId);
  ornekSayisi = 0;
  gonderilen = 0;
  bitisMesajiGonderildi = false;
  durmaNedeni = "";
  sonHata = 0;
  sonCizgiGorulme = millis();
  bitisBasladi = 0;
  if (mqtt.connected()) {
    String m = String(runId) + "," + hizSeviyesi + "," + yon + "," + parkur;
    mqtt.publish("cukur/basla", m.c_str());
  }
  kayitBaslangic = millis();
  kayitta = true;
  suruste = true;
}

void surusuBitir(const char* neden) {
  if (!suruste) return;
  motorDur();
  kayitta = false;
  suruste = false;
  durmaNedeni = neden;
  Serial.printf("Surus %d bitti (%s), %d ornek\n", runId, neden, ornekSayisi);
}

String satir(int i) {
  const Ornek& o = tampon[i];
  char b[128];
  snprintf(b, sizeof(b), "%d,%lu,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f,%d,%d,%d",
           runId, (unsigned long)o.t,
           o.a[0] / 16384.0, o.a[1] / 16384.0, o.a[2] / 16384.0,
           o.g[0] / 131.0, o.g[1] / 131.0, o.g[2] / 131.0,
           o.marker, hizSeviyesi, yon);
  return String(b);
}

// ------------------------- MQTT -------------------------
void mqttBaglan() {
  // Bağlanma denemesi birkaç saniye sürebilir; sürüş sırasında denenmez.
  if (suruste || mqtt.connected()) return;
  if (WiFi.softAPgetStationNum() == 0) return;
  if (millis() - sonMqttDeneme < 5000) return;
  sonMqttDeneme = millis();
  mqtt.setServer(brokerIp.c_str(), MQTT_PORT);
  wifiIstemci.setTimeout(2);
  String id = "cukur-arac-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (mqtt.connect(id.c_str(), MQTT_KULLANICI, MQTT_SIFRE)) {
    Serial.println("MQTT baglandi: " + brokerIp);
  }
}

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

// ------------------------- Web sayfası -------------------------
const char SAYFA[] PROGMEM = R"HTML(
<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Çukur Aracı</title>
<style>
body{font-family:sans-serif;max-width:480px;margin:auto;padding:12px;background:#f4f4f4}
.k{background:#fff;border-radius:8px;padding:12px;margin-bottom:10px}
label{display:block;margin:6px 0 2px}select,input{width:100%;padding:6px;font-size:16px}
button{width:100%;padding:12px;margin-top:8px;font-size:17px;border:0;border-radius:6px;color:#fff}
.y{background:#2e7d32}.r{background:#c62828}.m{background:#1565c0}.g{background:#555}
td{padding:2px 6px}
</style></head><body>
<h2>Çukur / Tümsek Aracı</h2>
<div class="k">
<label>Parkur</label><select id="p"><option value="engelli">Engelli parkur</option><option value="bos">Boş parkur</option></select>
<label>Hız seviyesi</label><select id="h"><option>1</option><option>2</option><option>3</option></select>
<label>Yön</label><select id="y"><option value="0">A → B</option><option value="1">B → A</option></select>
<button class="y" onclick="basla()">SÜRÜŞÜ BAŞLAT</button>
<button class="r" onclick="f('/durdur')">DURDUR</button>
<button class="m" onclick="location='/csv'">Son sürüşü CSV indir</button>
</div>
<div class="k"><table id="d"></table></div>
<div class="k">
<label>Veri alıcı bilgisayar (RabbitMQ) IP</label><input id="b">
<button class="g" onclick="f('/ayar?broker='+document.getElementById('b').value)">IP kaydet</button>
<button class="g" onclick="f('/ayar?benim=1')">Bu cihaz veri alıcısıdır</button>
<button class="g" onclick="f('/motortest?m=sol')">Motor testi: sol</button>
<button class="g" onclick="f('/motortest?m=sag')">Motor testi: sağ</button>
</div>
<script>
function f(u){fetch(u).then(r=>r.text()).then(t=>{if(t!='ok')alert(t)})}
function basla(){f('/basla?hiz='+h.value+'&yon='+y.value+'&parkur='+p.value)}
let ilk=1;
function yenile(){fetch('/durum').then(r=>r.json()).then(j=>{
 if(ilk){b.value=j.broker;ilk=0}
 let s='';for(const k in j)s+='<tr><td>'+k+'</td><td><b>'+j[k]+'</b></td></tr>';d.innerHTML=s})}
setInterval(yenile,500);yenile();
</script></body></html>
)HTML";

void webKur() {
  sunucu.on("/", []() { sunucu.send_P(200, "text/html; charset=utf-8", SAYFA); });

  sunucu.on("/basla", []() {
    if (suruste) { sunucu.send(200, "text/plain", "Surus zaten devam ediyor"); return; }
    if (!mpuHazir) { sunucu.send(200, "text/plain", "MPU-6050 bulunamadi, baglantiyi kontrol edin"); return; }
    surusuBaslat(sunucu.arg("hiz").toInt(), sunucu.arg("yon").toInt(), sunucu.arg("parkur"));
    sunucu.send(200, "text/plain", "ok");
  });

  sunucu.on("/durdur", []() { surusuBitir("kullanici durdurdu"); sunucu.send(200, "text/plain", "ok"); });

  sunucu.on("/durum", []() {
    bool s[CIZGI_SAYISI];
    cizgiOku(s);
    String cz;
    for (int i = 0; i < CIZGI_SAYISI; i++) cz += s[i] ? "1" : "0";
    String j = "{";
    j += "\"durum\":\"" + String(suruste ? "SÜRÜŞTE" : "bekliyor") + "\",";
    j += "\"run_id\":" + String(runId) + ",";
    j += "\"parkur\":\"" + parkur + "\",";
    j += "\"hiz\":" + String(hizSeviyesi) + ",";
    j += "\"yon\":" + String(yon) + ",";
    j += "\"ornek\":" + String(ornekSayisi) + ",";
    j += "\"gonderilen\":" + String(gonderilen) + ",";
    j += "\"durma_nedeni\":\"" + durmaNedeni + "\",";
    j += "\"mpu\":\"" + String(mpuHazir ? "hazir" : "YOK") + "\",";
    j += "\"az_g\":" + String(sonA[2] / 16384.0, 3) + ",";
    j += "\"cizgi\":\"" + cz + "\",";
    j += "\"yan_sensor\":" + String(sonMarker) + ",";
    j += "\"mqtt\":\"" + String(mqtt.connected() ? "bagli" : "bagli degil") + "\",";
    j += "\"broker\":\"" + brokerIp + "\"";
    j += "}";
    sunucu.send(200, "application/json", j);
  });

  sunucu.on("/csv", []() {
    int n = ornekSayisi;
    String ad = "run_" + String(runId) + "_" + parkur + "_h" + hizSeviyesi + "_y" + yon + ".csv";
    sunucu.sendHeader("Content-Disposition", "attachment; filename=" + ad);
    sunucu.setContentLength(CONTENT_LENGTH_UNKNOWN);
    sunucu.send(200, "text/csv", "");
    sunucu.sendContent("run_id,t_ms,ax,ay,az,gx,gy,gz,marker,speed_level,direction\n");
    String parca;
    for (int i = 0; i < n; i++) {
      parca += satir(i); parca += '\n';
      if (parca.length() > 2000) { sunucu.sendContent(parca); parca = ""; }
    }
    if (parca.length()) sunucu.sendContent(parca);
    sunucu.sendContent("");
  });

  sunucu.on("/ayar", []() {
    if (sunucu.hasArg("benim")) brokerIp = sunucu.client().remoteIP().toString();
    else if (sunucu.hasArg("broker")) brokerIp = sunucu.arg("broker");
    tercihler.putString("broker", brokerIp);
    mqtt.disconnect();
    sonMqttDeneme = 0;
    sunucu.send(200, "text/plain", "ok");
  });

  sunucu.on("/motortest", []() {
    if (suruste) { sunucu.send(200, "text/plain", "Surus sirasinda yapilamaz"); return; }
    if (sunucu.arg("m") == "sol") motorSur(HIZ_PWM[1], 0); else motorSur(0, HIZ_PWM[1]);
    delay(800);
    motorDur();
    sunucu.send(200, "text/plain", "ok");
  });

  sunucu.begin();
}

// ------------------------- Kurulum ve döngü -------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_IN1, OUTPUT); pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT); pinMode(PIN_IN4, OUTPUT);
  pinMode(PIN_ENA, OUTPUT); pinMode(PIN_ENB, OUTPUT);
  motorDur();
  for (int i = 0; i < CIZGI_SAYISI; i++) pinMode(PIN_CIZGI[i], INPUT);
  pinMode(PIN_YAN, INPUT);

  tercihler.begin("cukur", false);
  runId = tercihler.getInt("runId", 0);
  brokerIp = tercihler.getString("broker", VARSAYILAN_BROKER);

  tampon = (Ornek*)ps_malloc(sizeof(Ornek) * AZAMI_ORNEK);
  if (!tampon) tampon = (Ornek*)malloc(sizeof(Ornek) * AZAMI_ORNEK);
  if (!tampon) { Serial.println("Bellek ayrilamadi!"); while (true) delay(1000); }

  mpuHazir = mpuBaslat();
  Serial.println(mpuHazir ? "MPU-6050 hazir" : "MPU-6050 BULUNAMADI");

  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_ADI, AP_SIFRE);
  Serial.print("Wi-Fi: "); Serial.print(AP_ADI); Serial.print("  Adres: http://");
  Serial.println(WiFi.softAPIP());

  mqtt.setBufferSize(4096);
  webKur();

  xTaskCreatePinnedToCore(ornekGorevi, "ornek", 4096, nullptr, 2, nullptr, 0);
}

void loop() {
  sunucu.handleClient();
  if (suruste) {
    cizgiIzle();
    if (millis() - kayitBaslangic > AZAMI_SURE_MS) surusuBitir("azami sure");
    if (ornekSayisi >= AZAMI_ORNEK) surusuBitir("bellek doldu");
  }
  mqttBaglan();
  mqtt.loop();
  mqttGonder();
}
