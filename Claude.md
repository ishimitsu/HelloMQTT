MQTT学習用のサンプルプログラムを3つ実装してください。デバイスA, B, Cの3台構成です。

# 全体構成

- デバイスA（送信元・汎用PC/Mac、Python）: MQTTクライアント。起動後にHelloを送信し、応答を待つ。
- デバイスB（ブローカー・Raspberry Pi 4B、Python）: MQTTブローカー機能を持つプログラム。A-C間の通信を中継し、全メッセージをログ出力する。
- デバイスC（応答側・M5Stack Basic、C++/Arduino）: MQTTクライアント。Helloを受信したら応答を返し、画面表示も行う。

# トピック設計

- リクエスト用トピック: `mqtt-lab/hello/request`（A → C）
- レスポンス用トピック: `mqtt-lab/hello/response`（C → A）
- QoSは1、payloadはプレーンテキスト（JSON化しない）でよい。

# デバイスB: ブローカー兼ロガー（Python, Raspberry Pi 4B想定）

- 単一のPythonプログラムとして、MQTTブローカー機能を内包すること。外部のmosquitto等の別プロセスに依存する構成ではなく、Pythonプロセス単体で完結させる。
  - 実装には `amqtt`（aMQTT、Python製の非同期MQTTブローカー/クライアントライブラリ）の利用を想定している。利用可否・最新の使用方法を確認した上で実装すること。もし現時点でメンテナンス状況に懸念がある場合は、代替として「システムのMosquittoブローカーをsystemdまたはサブプロセスとして併用しつつ、同一Pythonプログラム内でワイルドカード購読(`#`)するロガー用クライアントを起動する」構成でもよい。採用した構成とその理由をREADMEに明記すること。
- 起動後、Ctrl+C（SIGINT）で終了するまで常駐すること。
- A, Cいずれかからメッセージを受信するたびに、以下の情報をデバッグログとして標準出力に表示すること。
  - 受信日時
  - 送信元クライアント（クライアントIDまたは可能な範囲で送信元情報）
  - トピック名
  - メッセージ本文
- 待受ポートはMQTT標準の1883番でよい。

# デバイスA: リクエスト送信・応答待受（Python, Mac/汎用PC想定）

- 標準的なMQTTクライアントライブラリ（`paho-mqtt`）を使用すること。
- 起動時にブローカーのホスト名/IPアドレスをコマンドライン引数または環境変数で指定できるようにすること（デフォルト値は仮でよい）。
- 実行フロー:
  1. ブローカーに接続する。
  2. レスポンス用トピック（`mqtt-lab/hello/response`）を購読する。
  3. リクエスト用トピック（`mqtt-lab/hello/request`）に `"Hello"` を送信する。
  4. 応答を受信したら、受信内容を表示して正常終了する（exit code 0）。
  5. 送信から10秒以内に応答が来ない場合、タイムアウトである旨のエラーメッセージを表示して異常終了する（exit code 1）。

# デバイスC: 応答・M5Stack表示（C++, Arduino IDE / M5Stack Basic想定）

- ライブラリは `M5Unified.h` と、MQTTクライアントとして `PubSubClient`（または類似の標準的なArduino用MQTTライブラリ）を使用すること。使用ライブラリはコード冒頭のコメントに明記すること。
- WiFi接続に必要なSSID・パスワードは、コード上部に以下のようなグローバル変数として定義すること（値はプレースホルダでよい。実装依頼者が実際の値に書き換える前提）。
  ```cpp
  const char* WIFI_SSID = "your-ssid";
  const char* WIFI_PASSWORD = "your-password";
  const char* MQTT_BROKER_HOST = "raspberrypi.local"; // またはIPアドレス
  const uint16_t MQTT_BROKER_PORT = 1883;
  ```
- setup()内でWiFi接続、MQTTブローカーへの接続、リクエスト用トピック（`mqtt-lab/hello/request`）の購読を行うこと。
- 接続が確立するまでの間、M5.Lcdに接続状況（WiFi接続中、MQTT接続中等）を表示すること（デバッグ用途）。
- loop()内でMQTT接続を維持すること（`PubSubClient`の`loop()`呼び出しと、切断時の再接続処理を含めること）。
- リクエスト用トピックでメッセージを受信したら、以下を行うこと。
  1. レスポンス用トピック（`mqtt-lab/hello/response`）に `"Hello!"` を送信する。
  2. 同時に、ディスプレイに "Hello!" を表示する。
  3. 5秒間表示を維持した後、画面をクリア（リセット）し、待受状態の表示に戻す。
  4. 上記2〜3の5秒間の待機処理は、`delay()`によるブロッキングで問題ない（学習用の単純な実装のため、非同期化は不要）。

# 成果物として求めるもの

- 以下のディレクトリ構成でファイルを生成すること。
  ```
  mqtt-lab/
  ├── device_b_broker/       # デバイスB（Raspberry Pi）
  │   ├── broker.py
  │   └── requirements.txt
  ├── device_a_sender/       # デバイスA（Mac）
  │   ├── sender.py
  │   └── requirements.txt
  ├── device_c_m5stack/      # デバイスC（M5Stack、Arduino IDE用）
  │   └── device_c_m5stack.ino
  └── README.md
  ```
- README.mdには、以下を記載すること。
  - 各デバイスでの実行順序（B起動 → C起動・接続確認 → A実行、という順序を明記）
  - デバイスBの依存ライブラリのインストール方法（`pip install -r requirements.txt`）
  - デバイスCのArduino IDE側で事前にインストールが必要なライブラリ一覧
  - 動作確認の手順（何を確認すればうまく動いているとみなせるか）
  - デバイスBのブローカー実装として何を採用したか（amqttか、Mosquitto併用か）とその理由

# 制約・注意事項

- 認証やTLSは学習用途のため実装不要（平文・無認証のMQTT通信でよい）。ただしREADMEに「本番運用時はユーザー認証・TLS化が必要」である旨を一言注記すること。
- エラーハンドリングは最低限（接続失敗時にエラーメッセージを出す程度）でよいが、デバイスAのタイムアウト処理だけは仕様通り厳密に実装すること。
