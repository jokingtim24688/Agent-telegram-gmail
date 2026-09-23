// Loupe glasses firmware — XIAO ESP32S3 Sense
//
// What it does:
//   * Button press (or "/snap" from the AI account) -> take a JPEG -> post it to the
//     Loupe Telegram group through the glasses bot.
//   * If Telegram fails, email the same frame from the glasses' own Gmail account
//     to the AI's Gmail account (backup path).
//   * Listens in the group ONLY to the AI account (matched by numeric user id, never
//     by display name — names are not unique and can be copied).
//
// Credentials live in NVS flash, written by the desktop app over USB serial:
//   {"cmd":"provision", "wifi":[{"ssid":"..","pass":".."}], "tg_token":"..",
//    "tg_chat":"-100..", "tg_from":"123", "gm_user":"..", "gm_pass":"..",
//    "gm_to":"..", "btn_pin":1, "poll_s":5}
// Other serial commands: {"cmd":"status"}, {"cmd":"snap"}, {"cmd":"wipe"}.
// Every reply is one JSON line; log lines start with "# ".

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <time.h>
#include "esp_camera.h"
#include "mbedtls/base64.h"
#include "ca_certs.h"

static const char *FW_VERSION = "1.0.0";

// ---- XIAO ESP32S3 Sense camera pins ----
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  10
#define SIOD_GPIO_NUM  40
#define SIOC_GPIO_NUM  39
#define Y9_GPIO_NUM    48
#define Y8_GPIO_NUM    11
#define Y7_GPIO_NUM    12
#define Y6_GPIO_NUM    14
#define Y5_GPIO_NUM    16
#define Y4_GPIO_NUM    18
#define Y3_GPIO_NUM    17
#define Y2_GPIO_NUM    15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM  47
#define PCLK_GPIO_NUM  13

#define LED_PIN 21  // orange user LED, active LOW

struct Config {
  String wifiJson = "[]";
  String tgToken, tgChat, tgFrom;
  String gmUser, gmPass, gmTo;
  int btnPin = 1;        // D0; wire a momentary button from D0 to GND
  int pollSeconds = 5;
  bool tlsInsecure = false;
  bool configured() const {
    return tgToken.length() && tgChat.length() && tgFrom.length() && wifiJson.length() > 2;
  }
} cfg;

Preferences prefs;
WiFiMulti wifiMulti;
bool cameraOk = false;
bool wifiEverConnected = false;
bool skipOldUpdates = true;
long long tgOffset = 0;
unsigned long lastPoll = 0;
unsigned long lastWifiTry = 0;
String lastSend = "none";
String serialLine;
int lastButton = HIGH;
unsigned long buttonChangedAt = 0;

// ---------------------------------------------------------------- helpers

void logLine(const String &s) {
  Serial.print("# ");
  Serial.println(s);
}

void led(bool on) { digitalWrite(LED_PIN, on ? LOW : HIGH); }

void blink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    led(true);
    delay(ms);
    led(false);
    delay(ms);
  }
}

void secure(WiFiClientSecure &c) {
  if (cfg.tlsInsecure) c.setInsecure();
  else c.setCACert(CA_BUNDLE);
}

String readLine(WiFiClient &c, uint32_t timeoutMs) {
  String line;
  uint32_t start = millis();
  while (millis() - start < timeoutMs) {
    while (c.available()) {
      char ch = c.read();
      if (ch == '\n') {
        line.trim();
        return line;
      }
      if (line.length() < 512) line += ch;
    }
    if (!c.connected()) break;
    delay(5);
  }
  line.trim();
  return line;
}

String b64(const String &s) {
  size_t need = 4 * ((s.length() + 2) / 3) + 1, olen = 0;
  unsigned char *buf = (unsigned char *)malloc(need);
  if (!buf) return "";
  mbedtls_base64_encode(buf, need, &olen, (const unsigned char *)s.c_str(), s.length());
  String out((const char *)buf);
  free(buf);
  return out;
}

void reply(JsonDocument &d) {
  serializeJson(d, Serial);
  Serial.println();
}

// ---------------------------------------------------------------- config

void loadConfig() {
  prefs.begin("loupe", true);
  cfg.wifiJson = prefs.getString("wifi", "[]");
  cfg.tgToken = prefs.getString("tg_token", "");
  cfg.tgChat = prefs.getString("tg_chat", "");
  cfg.tgFrom = prefs.getString("tg_from", "");
  cfg.gmUser = prefs.getString("gm_user", "");
  cfg.gmPass = prefs.getString("gm_pass", "");
  cfg.gmTo = prefs.getString("gm_to", "");
  cfg.btnPin = prefs.getInt("btn_pin", 1);
  cfg.pollSeconds = prefs.getInt("poll_s", 5);
  cfg.tlsInsecure = prefs.getBool("tls_insecure", false);
  prefs.end();
}

void addWifiNetworks() {
  JsonDocument doc;
  if (deserializeJson(doc, cfg.wifiJson)) return;
  for (JsonObject n : doc.as<JsonArray>()) {
    const char *ssid = n["ssid"] | "";
    const char *pass = n["pass"] | "";
    if (strlen(ssid)) wifiMulti.addAP(ssid, pass);
  }
}

// ---------------------------------------------------------------- camera

bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;
  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_SVGA;  // 800x600: enough for OCR, small enough to send fast
  c.jpeg_quality = 12;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    logLine("camera init failed: 0x" + String(err, HEX));
    return false;
  }
  return true;
}

// ---------------------------------------------------------------- telegram

bool sendTelegramPhoto(camera_fb_t *fb, const char *reason) {
  WiFiClientSecure c;
  secure(c);
  if (!c.connect("api.telegram.org", 443)) {
    logLine("telegram: connect failed");
    return false;
  }
  const String B = "----LoupeFrameBoundary";
  String head = "--" + B + "\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n" + cfg.tgChat + "\r\n" +
                "--" + B + "\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n#capture " + reason + "\r\n" +
                "--" + B + "\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"frame.jpg\"\r\n" +
                "Content-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + B + "--\r\n";
  size_t len = head.length() + fb->len + tail.length();

  c.print("POST /bot" + cfg.tgToken + "/sendPhoto HTTP/1.1\r\n");
  c.print("Host: api.telegram.org\r\n");
  c.print("Content-Type: multipart/form-data; boundary=" + B + "\r\n");
  c.print("Content-Length: " + String(len) + "\r\n");
  c.print("Connection: close\r\n\r\n");
  c.print(head);
  for (size_t i = 0; i < fb->len; i += 1024) {
    size_t n = fb->len - i;
    if (n > 1024) n = 1024;
    c.write(fb->buf + i, n);
  }
  c.print(tail);

  String status = readLine(c, 20000);
  bool ok = status.indexOf(" 200") > 0;
  if (!ok) logLine("telegram: " + (status.length() ? status : String("no response")));
  c.stop();
  return ok;
}

bool sendTelegramText(const String &text) {
  WiFiClientSecure c;
  secure(c);
  HTTPClient http;
  if (!http.begin(c, "https://api.telegram.org/bot" + cfg.tgToken + "/sendMessage")) return false;
  http.addHeader("Content-Type", "application/json");
  JsonDocument d;
  d["chat_id"] = cfg.tgChat;
  d["text"] = text;
  d["disable_notification"] = true;
  String body;
  serializeJson(d, body);
  int code = http.POST(body);
  http.end();
  return code == 200;
}

String statusText() {
  return "#status fw=" + String(FW_VERSION) + " rssi=" + String(WiFi.RSSI()) +
         " heap=" + String(ESP.getFreeHeap() / 1024) + "k psram=" + String(ESP.getFreePsram() / 1024) +
         "k camera=" + (cameraOk ? "ok" : "fail") + " last_send=" + lastSend;
}

// ---------------------------------------------------------------- gmail backup

bool smtpExpect(WiFiClientSecure &c, int code) {
  for (int guard = 0; guard < 40; guard++) {  // multi-line replies: "250-..." then "250 ..."
    String line = readLine(c, 15000);
    if (line.length() < 3) {
      logLine("smtp: timeout");
      return false;
    }
    if (line.length() == 3 || line[3] == ' ') {
      int got = line.substring(0, 3).toInt();
      if (got != code) logLine("smtp: " + line);
      return got == code;
    }
  }
  return false;
}

bool smtpSend(WiFiClientSecure &c, const String &cmd, int code) {
  c.print(cmd);
  c.print("\r\n");
  return smtpExpect(c, code);
}

bool sendGmailPhoto(camera_fb_t *fb, const char *reason) {
  if (!cfg.gmUser.length() || !cfg.gmPass.length() || !cfg.gmTo.length()) return false;
  WiFiClientSecure c;
  secure(c);
  if (!c.connect("smtp.gmail.com", 465)) {
    logLine("gmail: connect failed");
    return false;
  }
  bool ok = smtpExpect(c, 220) && smtpSend(c, "EHLO loupe-glasses", 250) &&
            smtpSend(c, "AUTH LOGIN", 334) && smtpSend(c, b64(cfg.gmUser), 334) &&
            smtpSend(c, b64(cfg.gmPass), 235) && smtpSend(c, "MAIL FROM:<" + cfg.gmUser + ">", 250) &&
            smtpSend(c, "RCPT TO:<" + cfg.gmTo + ">", 250) && smtpSend(c, "DATA", 354);
  if (!ok) {
    c.stop();
    return false;
  }
  const char *B = "loupe-frame-boundary";
  c.print("From: Loupe glasses <" + cfg.gmUser + ">\r\n");
  c.print("To: <" + cfg.gmTo + ">\r\n");
  c.print(String("Subject: [loupe] capture ") + reason + "\r\n");
  c.print("MIME-Version: 1.0\r\n");
  c.print(String("Content-Type: multipart/mixed; boundary=\"") + B + "\"\r\n\r\n");
  c.print(String("--") + B + "\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n");
  c.print(String("Telegram was unreachable, so the glasses sent this frame by email (") + reason + ").\r\n");
  c.print(String("--") + B + "\r\nContent-Type: image/jpeg; name=\"frame.jpg\"\r\n");
  c.print("Content-Transfer-Encoding: base64\r\n");
  c.print("Content-Disposition: attachment; filename=\"frame.jpg\"\r\n\r\n");

  // 57 raw bytes -> one 76-char base64 line. Batch ~13 lines per TLS write.
  unsigned char line[80];
  char out[1100];
  size_t outLen = 0;
  for (size_t i = 0; i < fb->len; i += 57) {
    size_t n = fb->len - i, olen = 0;
    if (n > 57) n = 57;
    mbedtls_base64_encode(line, sizeof(line), &olen, fb->buf + i, n);
    memcpy(out + outLen, line, olen);
    outLen += olen;
    out[outLen++] = '\r';
    out[outLen++] = '\n';
    if (outLen > 1000) {
      c.write((const uint8_t *)out, outLen);
      outLen = 0;
    }
  }
  if (outLen) c.write((const uint8_t *)out, outLen);
  c.print(String("--") + B + "--\r\n.\r\n");
  ok = smtpExpect(c, 250);
  smtpSend(c, "QUIT", 221);
  c.stop();
  return ok;
}

// ---------------------------------------------------------------- capture

bool captureAndSend(const char *reason) {
  if (!cameraOk) {
    logLine("capture skipped: camera not ready");
    return false;
  }
  led(true);
  camera_fb_t *fb = esp_camera_fb_get();  // drop the buffered (stale) frame
  if (fb) esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();
  if (!fb) {
    led(false);
    logLine("capture failed: no frame");
    blink(3, 80);
    return false;
  }
  logLine("frame " + String(fb->len / 1024) + "k (" + reason + ")");

  bool ok = false;
  if (WiFi.status() == WL_CONNECTED) {
    if (sendTelegramPhoto(fb, reason)) {
      ok = true;
      lastSend = "telegram";
    } else if (sendGmailPhoto(fb, reason)) {
      ok = true;
      lastSend = "gmail";
    }
  } else {
    logLine("capture not sent: no Wi-Fi");
  }
  if (!ok) lastSend = "failed";
  esp_camera_fb_return(fb);
  led(false);
  if (ok) blink(1, 150);
  else blink(3, 80);
  return ok;
}

// ---------------------------------------------------------------- group listener

// Obeys only messages that are (a) in the Loupe group and (b) from the AI account's user id.
void pollTelegram() {
  WiFiClientSecure c;
  secure(c);
  HTTPClient http;
  char url[256];
  if (skipOldUpdates) {
    snprintf(url, sizeof(url), "https://api.telegram.org/bot%s/getUpdates?timeout=0&limit=5&offset=-1",
             cfg.tgToken.c_str());
  } else {
    snprintf(url, sizeof(url), "https://api.telegram.org/bot%s/getUpdates?timeout=0&limit=5&offset=%lld",
             cfg.tgToken.c_str(), tgOffset);
  }
  if (!http.begin(c, url)) return;
  int code = http.GET();
  if (code != 200) {
    logLine("poll: HTTP " + String(code));
    http.end();
    return;
  }
  String body = http.getString();
  http.end();

  JsonDocument filter;
  filter["result"][0]["update_id"] = true;
  filter["result"][0]["message"]["chat"]["id"] = true;
  filter["result"][0]["message"]["from"]["id"] = true;
  filter["result"][0]["message"]["text"] = true;
  JsonDocument doc;
  if (deserializeJson(doc, body, DeserializationOption::Filter(filter))) return;

  long long chatWanted = atoll(cfg.tgChat.c_str());
  long long fromWanted = atoll(cfg.tgFrom.c_str());
  for (JsonObject u : doc["result"].as<JsonArray>()) {
    tgOffset = u["update_id"].as<long long>() + 1;
    if (skipOldUpdates) continue;  // don't replay commands queued while we were off
    JsonObject m = u["message"];
    if (m["chat"]["id"].as<long long>() != chatWanted) continue;
    if (m["from"]["id"].as<long long>() != fromWanted) continue;
    const char *text = m["text"] | "";
    // Accept "/snap" and "/snap@this_bot" (the AI addresses commands to us explicitly
    // so they reach the bot even with group privacy mode on).
    if (strncmp(text, "/snap", 5) == 0) captureAndSend("remote");
    else if (strncmp(text, "/ping", 5) == 0) sendTelegramText(statusText());
  }
  skipOldUpdates = false;
}

// ---------------------------------------------------------------- serial provisioning

void handleCommand(const String &line) {
  JsonDocument in, out;
  if (deserializeJson(in, line)) {
    out["ok"] = false;
    out["error"] = "not JSON";
    reply(out);
    return;
  }
  String cmd = in["cmd"] | "";

  if (cmd == "provision") {
    prefs.begin("loupe", false);
    if (in["wifi"].is<JsonArray>()) {
      String w;
      serializeJson(in["wifi"], w);
      prefs.putString("wifi", w);
    }
    const char *keys[] = {"tg_token", "tg_chat", "tg_from", "gm_user", "gm_pass", "gm_to"};
    for (const char *k : keys) {
      if (in[k].is<const char *>()) prefs.putString(k, in[k].as<const char *>());
    }
    if (in["btn_pin"].is<int>()) prefs.putInt("btn_pin", in["btn_pin"].as<int>());
    if (in["poll_s"].is<int>()) prefs.putInt("poll_s", in["poll_s"].as<int>());
    if (in["tls_insecure"].is<bool>()) prefs.putBool("tls_insecure", in["tls_insecure"].as<bool>());
    prefs.end();
    out["ok"] = true;
    out["detail"] = "saved; restarting";
    reply(out);
    Serial.flush();
    delay(300);
    ESP.restart();
  } else if (cmd == "status") {
    out["ok"] = true;
    out["fw"] = FW_VERSION;
    out["configured"] = cfg.configured();
    out["camera"] = cameraOk;
    out["wifi"] = WiFi.status() == WL_CONNECTED ? WiFi.SSID() : String("");
    out["rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
    out["gmail_backup"] = cfg.gmUser.length() > 0;
    out["last_send"] = lastSend;
    out["btn_pin"] = cfg.btnPin;
    reply(out);
  } else if (cmd == "snap") {
    out["ok"] = captureAndSend("serial");
    out["last_send"] = lastSend;
    reply(out);
  } else if (cmd == "wipe") {
    prefs.begin("loupe", false);
    prefs.clear();
    prefs.end();
    out["ok"] = true;
    out["detail"] = "wiped; restarting";
    reply(out);
    Serial.flush();
    delay(300);
    ESP.restart();
  } else {
    out["ok"] = false;
    out["error"] = "unknown cmd";
    reply(out);
  }
}

void pumpSerial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (serialLine.length()) handleCommand(serialLine);
      serialLine = "";
    } else if (serialLine.length() < 2048) {
      serialLine += ch;
    }
  }
}

// ---------------------------------------------------------------- main

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  led(false);
  delay(500);
  logLine(String("loupe glasses fw ") + FW_VERSION);

  loadConfig();
  pinMode(cfg.btnPin, INPUT_PULLUP);
  cameraOk = initCamera();

  if (!cfg.configured()) {
    logLine("not provisioned; waiting for the desktop app over USB");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);  // modem sleep between polls saves battery
  addWifiNetworks();
}

void loop() {
  pumpSerial();
  if (!cfg.configured()) {
    delay(20);
    return;
  }

  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiTry > 10000) {
    lastWifiTry = millis();
    if (wifiMulti.run(8000) == WL_CONNECTED) {
      logLine("wifi: " + WiFi.SSID() + " " + WiFi.localIP().toString());
      if (!wifiEverConnected) configTime(0, 0, "pool.ntp.org", "time.google.com");
      wifiEverConnected = true;
    }
  }

  int b = digitalRead(cfg.btnPin);
  if (b != lastButton && millis() - buttonChangedAt > 40) {
    buttonChangedAt = millis();
    lastButton = b;
    if (b == LOW) captureAndSend("button");
  }

  if (WiFi.status() == WL_CONNECTED && millis() - lastPoll > (unsigned long)cfg.pollSeconds * 1000UL) {
    lastPoll = millis();
    pollTelegram();
  }
  delay(10);
}
