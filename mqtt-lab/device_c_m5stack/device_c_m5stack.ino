/*
 * デバイスC: 応答・M5Stack表示 (M5Stack Basic / Arduino IDE 想定)
 *
 * 使用ライブラリ:
 *   - M5Unified            (M5Stack公式の統合ライブラリ。M5.Lcd / M5.Display を提供)
 *   - PubSubClient         (Nick O'Leary製のArduino用MQTTクライアント)
 *   - WiFi.h               (arduino-esp32 に同梱。別途インストール不要)
 *
 * 動作:
 *   setup()  : WiFi接続 → MQTTブローカー接続 → リクエスト用トピックを購読
 *   loop()   : MQTT接続を維持 (切断時は再接続)
 *   受信時   : レスポンス用トピックに "Hello!" を送信し、画面に "Hello!" を表示。
 *              5秒間表示を維持したのち画面をクリアし、待受表示に戻す。
 *
 * 注意 (PubSubClientの制約):
 *   PubSubClient は publish が QoS 0 固定 (subscribe は QoS 0/1 が可能)。
 *   このため request の購読は QoS 1、response の送信は QoS 0 となる。
 *   また既定のバッファは256バイト、keepaliveは15秒。本サンプルの短い
 *   ペイロードでは問題にならない。
 */

#include <M5Unified.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ---- 設定: 実際の値に書き換えてください ------------------------------------

const char* WIFI_SSID       = "your-ssid";
const char* WIFI_PASSWORD   = "your-password";

// ブローカー(デバイスB / Raspberry Pi)のIPアドレスを指定する。
// ホスト名 "raspberrypi.local" (mDNS) はESP32側の環境に依存して解決できない
// 場合があるため、IPアドレスでの指定を推奨する。
const char* MQTT_BROKER_HOST = "192.168.1.100";
const uint16_t MQTT_BROKER_PORT = 1883;

// ---------------------------------------------------------------------------

const char* MQTT_CLIENT_ID   = "device-c";
const char* REQUEST_TOPIC    = "mqtt-lab/hello/request";
const char* RESPONSE_TOPIC   = "mqtt-lab/hello/response";
const uint8_t SUBSCRIBE_QOS  = 1;

const char* RESPONSE_PAYLOAD = "Hello!";
const uint32_t DISPLAY_HOLD_MS = 5000;  // "Hello!" を表示し続ける時間

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// ---- 画面表示ヘルパ --------------------------------------------------------

// 接続状況などのステータスを1行表示する (デバッグ用途)
void showStatus(const char* line1, const char* line2 = nullptr) {
  M5.Lcd.fillScreen(TFT_BLACK);
  M5.Lcd.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(10, 20);
  M5.Lcd.println(line1);
  if (line2 != nullptr) {
    M5.Lcd.setCursor(10, 50);
    M5.Lcd.println(line2);
  }
}

// リクエスト待受中の画面
void showWaitingScreen() {
  M5.Lcd.fillScreen(TFT_BLACK);
  M5.Lcd.setTextColor(TFT_DARKGREY, TFT_BLACK);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(10, 20);
  M5.Lcd.println("Device C");
  M5.Lcd.setCursor(10, 50);
  M5.Lcd.println("Waiting for request...");
  M5.Lcd.setCursor(10, 90);
  M5.Lcd.println(REQUEST_TOPIC);
}

// 応答時の画面 ("Hello!" を大きく表示)
void showHelloScreen() {
  M5.Lcd.fillScreen(TFT_BLACK);
  M5.Lcd.setTextColor(TFT_GREEN, TFT_BLACK);
  M5.Lcd.setTextSize(5);
  M5.Lcd.setCursor(40, 100);
  M5.Lcd.println(RESPONSE_PAYLOAD);
}

// ---- WiFi / MQTT -----------------------------------------------------------

void connectWiFi() {
  showStatus("WiFi connecting...", WIFI_SSID);
  Serial.printf("WiFi connecting to %s\n", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  Serial.print("WiFi connected. IP: ");
  Serial.println(WiFi.localIP());
  showStatus("WiFi connected", WiFi.localIP().toString().c_str());
  delay(1000);
}

// リクエスト受信時のコールバック。
// 5秒間の待機は delay() によるブロッキングで問題ない (学習用の単純な実装のため)。
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message;
  message.reserve(length);
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.printf("Received [%s] %s\n", topic, message.c_str());

  // 1. レスポンス用トピックに "Hello!" を送信する
  bool ok = mqttClient.publish(RESPONSE_TOPIC, RESPONSE_PAYLOAD);
  Serial.printf("Published [%s] %s -> %s\n", RESPONSE_TOPIC, RESPONSE_PAYLOAD,
                ok ? "OK" : "FAILED");

  // 2. 同時に、ディスプレイに "Hello!" を表示する
  showHelloScreen();

  // 3. 5秒間表示を維持した後、画面をクリアして待受表示に戻す
  delay(DISPLAY_HOLD_MS);
  showWaitingScreen();
}

// MQTTブローカーへ接続し、リクエスト用トピックを購読する。
// 接続できるまでリトライする。
void connectMqtt() {
  while (!mqttClient.connected()) {
    showStatus("MQTT connecting...", MQTT_BROKER_HOST);
    Serial.printf("MQTT connecting to %s:%u\n", MQTT_BROKER_HOST, MQTT_BROKER_PORT);

    // 学習用途のため無認証 (ユーザー名/パスワードなし) で接続する
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
      Serial.println("MQTT connected");
      mqttClient.subscribe(REQUEST_TOPIC, SUBSCRIBE_QOS);
      Serial.printf("Subscribed to %s (QoS %u)\n", REQUEST_TOPIC, SUBSCRIBE_QOS);
      showWaitingScreen();
    } else {
      Serial.printf("MQTT connect failed, rc=%d. retry in 5s\n", mqttClient.state());
      showStatus("MQTT connect failed", "retrying...");
      delay(5000);
    }
  }
}

// ---- Arduino エントリポイント ----------------------------------------------

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(115200);
  M5.Lcd.setRotation(1);
  showStatus("Starting...");

  connectWiFi();

  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setCallback(onMqttMessage);
  connectMqtt();
}

void loop() {
  M5.update();

  // WiFiが切れていれば張り直す
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost. reconnecting...");
    connectWiFi();
  }

  // MQTTが切れていれば張り直す (購読もやり直す)
  if (!mqttClient.connected()) {
    Serial.println("MQTT lost. reconnecting...");
    connectMqtt();
  }

  // MQTT接続の維持 (keepalive送信と受信処理)
  mqttClient.loop();
}
