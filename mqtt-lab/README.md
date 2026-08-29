# mqtt-lab — MQTT学習用サンプル (デバイスA / B / C)

3台構成でMQTTのリクエスト・レスポンスを体験するためのサンプルです。

| デバイス | 役割 | 想定ハード | 言語 / 主要ライブラリ |
|---|---|---|---|
| **A** | リクエスト送信・応答待受 | Mac / 汎用PC | Python / `paho-mqtt` |
| **B** | MQTTブローカー兼ロガー | Raspberry Pi 4B | Python / `amqtt` |
| **C** | 応答・画面表示 | M5Stack Basic | C++ / `M5Unified` + `PubSubClient` |

## トピック設計

| トピック | 向き | ペイロード |
|---|---|---|
| `mqtt-lab/hello/request` | A → C | `Hello` |
| `mqtt-lab/hello/response` | C → A | `Hello!` |

ペイロードはプレーンテキスト（JSONではありません）。

### QoSについて

| 経路 | QoS | 理由 |
|---|---|---|
| A → `request` の送信 | 1 | paho-mqtt はQoS 1で送信可能 |
| C の `request` 購読 | 1 | PubSubClient は購読はQoS 0/1に対応 |
| C → `response` の送信 | **0** | **PubSubClient は publish がQoS 0固定**（公式READMEのLimitationsに明記） |
| A の `response` 購読 | 1 | 送信側がQoS 0のため実効はQoS 0 |

全経路をQoS 1にしたい場合は、デバイスCのライブラリを `256dpi/arduino-mqtt` などQoS 1のpublishに対応したものへ差し替える必要があります。本サンプルは情報量の多い定番ライブラリである PubSubClient を優先し、この1経路のみQoS 0としています。

## ディレクトリ構成

```
mqtt-lab/
├── device_b_broker/          # デバイスB（Raspberry Pi）
│   ├── broker.py
│   └── requirements.txt
├── device_a_sender/          # デバイスA（Mac）
│   ├── sender.py
│   └── requirements.txt
├── device_c_m5stack/         # デバイスC（M5Stack、Arduino IDE用）
│   └── device_c_m5stack.ino
└── README.md
```

---

## デバイスBのブローカー実装として採用したもの: amqtt

**`amqtt`（aMQTT）を採用しました。** Mosquitto併用構成は採用していません。理由は2点です。

**1. メンテナンス状況に問題がなかった**

検証時点で最新版は **0.12.0（2026-08-12リリース）**、PyPIの分類は `Development Status :: 5 - Production/Stable`、対応Pythonは 3.10〜3.14 です。「Pythonプロセス単体で完結させる」という要件を、外部プロセスなしでそのまま満たせます。

**2. Mosquitto併用構成では「送信元クライアントID」をログできない**

MQTT 3.1.1 の PUBLISH パケットには送信元クライアントIDが含まれません。そのため Mosquitto にワイルドカード（`#`）購読のロガークライアントを付ける構成では、トピック・本文・受信日時は取れても**どのクライアントが送ったかは原理的に取得できません**。

amqtt ならブローカーのイベントを直接フックできるため、`client_id` を含めた完全なログが出せます。

```python
class MessageLoggerPlugin(BasePlugin[BaseContext]):
    async def on_broker_message_received(self, *, client_id=None, message=None, **_):
        ...
```

---

## 必要環境

| デバイス | 要件 |
|---|---|
| B | **Python 3.10以上**（amqttの要件）。Raspberry Pi OS Bookworm は Python 3.11 のため追加対応は不要です |
| A | Python 3.10以上を推奨 |
| C | Arduino IDE + ESP32ボードマネージャ（M5Stack Basic を選択） |

## セットアップ

### デバイスB（Raspberry Pi）

```bash
cd mqtt-lab/device_b_broker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### デバイスA（Mac / 汎用PC）

```bash
cd mqtt-lab/device_a_sender
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### デバイスC（M5Stack）

Arduino IDE のライブラリマネージャから、以下を**事前にインストール**してください。

| ライブラリ | 用途 | 備考 |
|---|---|---|
| **M5Unified** | M5Stack本体・画面制御 | 依存する `M5GFX` も同時に入ります |
| **PubSubClient** | MQTTクライアント | 作者: Nick O'Leary |

`WiFi.h` は arduino-esp32 に同梱のため、別途インストールは不要です。

ボード設定は **Board: "M5Stack-Core-ESP32"（または "M5Stack Basic"）** を選択してください。

---

## 実行順序

**必ず B → C → A の順に起動してください。**

この順序が必要なのは、購読者が存在しないトピックへ送られたメッセージはブローカーで破棄されるためです。QoS 1 でも、永続セッションを使っていない本サンプルではCが未接続の間に届いたリクエストは保持されません。Cが接続する前にAを実行すると、リクエストは誰にも届かず10秒でタイムアウトします。

### 1. デバイスB: ブローカーを起動

```bash
cd mqtt-lab/device_b_broker
source .venv/bin/activate
python3 broker.py
```

`0.0.0.0:1883` で待ち受けます。終了は **Ctrl+C**。以降、全メッセージがこのコンソールに出力されます。

デバイスAから接続するために、Raspberry PiのIPアドレスを控えておいてください。

```bash
hostname -I
```

### 2. デバイスC: スケッチを書き込んで接続を確認

[device_c_m5stack/device_c_m5stack.ino](device_c_m5stack/device_c_m5stack.ino) の冒頭を自分の環境に合わせて書き換えます。

```cpp
const char* WIFI_SSID       = "your-ssid";
const char* WIFI_PASSWORD   = "your-password";
const char* MQTT_BROKER_HOST = "192.168.1.100";  // デバイスBのIPアドレス
const uint16_t MQTT_BROKER_PORT = 1883;
```

> **`raspberrypi.local` について**: mDNS名での指定はESP32側のlwIP設定やネットワーク環境に依存して解決できない場合があります。確実に動かすため **IPアドレスでの指定を推奨**します。

書き込み後、M5Stackの画面が `Starting...` → `WiFi connecting...` → `WiFi connected` → `MQTT connecting...` と遷移し、最終的に **`Waiting for request...`** が表示されれば接続成功です。

同時に、デバイスBのコンソールにも接続が出ます。

```
[2026-08-29 21:15:00.123] CONNECT     client_id=device-c
[2026-08-29 21:15:00.140] SUBSCRIBE   client_id=device-c  topic=mqtt-lab/hello/request  qos=1
```

**この2つが出るまでは、次のデバイスAに進まないでください。**

### 3. デバイスA: リクエストを送信

ブローカーのホストは **コマンドライン引数 > 環境変数 > コード内の既定値** の優先順位で決まります。

```bash
cd mqtt-lab/device_a_sender
source .venv/bin/activate

# コマンドライン引数で指定
python3 sender.py --host 192.168.1.100

# 環境変数で指定
MQTT_BROKER_HOST=192.168.1.100 python3 sender.py

# どちらも省略した場合は sender.py 冒頭の BROKER_HOST が使われます
python3 sender.py
```

既定値を固定したい場合は [device_a_sender/sender.py](device_a_sender/sender.py) 冒頭の変数を書き換えてください。

```python
BROKER_HOST = "192.168.1.100"
BROKER_PORT = 1883
```

---

## 動作確認の手順

うまく動いていれば、以下がすべて観測できます。

### ✅ デバイスA の出力（成功時）

```
ブローカーに接続しました: 192.168.1.100:1883
購読しました: mqtt-lab/hello/response (QoS 1)
送信しました: mqtt-lab/hello/request <- 'Hello' (QoS 1)
応答を受信しました: mqtt-lab/hello/response -> 'Hello!'
```

終了コードを確認します。

```bash
echo $?    # → 0
```

### ✅ デバイスB の出力

`request` と `response` の**両方**が、それぞれ正しい送信元とともに記録されます。

```
[2026-08-29 21:15:01.507] MESSAGE  from=device-a  topic=mqtt-lab/hello/request   qos=1  payload='Hello'
[2026-08-29 21:15:01.508] MESSAGE  from=device-c  topic=mqtt-lab/hello/response  qos=0  payload='Hello!'
```

`from=` が `device-a` / `device-c` と正しく出ていること、受信日時・トピック・本文が揃っていることを確認してください。

### ✅ デバイスC の画面

`Waiting for request...` → **`Hello!` が緑の大きな文字で表示** → **5秒後に自動で `Waiting for request...` に戻る**。

この5秒間の遷移が確認できれば成功です。何度でも繰り返しデバイスAを実行できます。

### ✅ タイムアウト動作の確認

デバイスCの電源を切る（またはWiFiを切断する）状態でデバイスAを実行します。

```bash
python3 sender.py --host 192.168.1.100
# → 約10秒後
# エラー: タイムアウトしました。mqtt-lab/hello/response への応答が 10秒以内に届きませんでした ...
echo $?    # → 1
```

**10秒程度で終了し、終了コードが 1 になること**を確認してください。

### うまくいかないときは

| 症状 | 確認すること |
|---|---|
| Aが「接続できません」 | Bが起動しているか。IPアドレスが正しいか。同じLAN上にいるか。Raspberry Piのファイアウォールが1883番を通すか |
| Aが10秒でタイムアウト | Bのコンソールに `CONNECT client_id=device-c` と `SUBSCRIBE ...` が出ているか。出ていなければCが接続できていません |
| Cの画面が `MQTT connect failed` | `MQTT_BROKER_HOST` のIPアドレスを確認。`raspberrypi.local` を使っている場合はIP直指定に変更 |
| Cの画面が `WiFi connecting...` のまま | SSID / パスワードを確認。ESP32は**2.4GHz帯のみ**対応です（5GHz専用SSIDには接続できません） |
| Bで `Address already in use` | すでに mosquitto 等が1883番を使用しています。`sudo systemctl stop mosquitto` で停止してください |

---

## セキュリティに関する注意

> ⚠️ **本サンプルは学習用途のため、認証もTLSも使わない平文・無認証のMQTT通信です。**
> ブローカーは匿名接続をすべて許可しており、通信内容はネットワーク上をそのまま流れます。
> **本番運用時にはユーザー認証（`amqtt.plugins.authentication.FileAuthPlugin` 等）とTLS化が必須です。**

---

## 既知の課題

### 🔑 WiFi認証情報がソースコードに直書きされている（未対応）

[device_c_m5stack/device_c_m5stack.ino](device_c_m5stack/device_c_m5stack.ino) では、WiFiのSSIDとパスワードをソースコード冒頭のグローバル変数に直接記述しています。

```cpp
const char* WIFI_SSID     = "your-ssid";
const char* WIFI_PASSWORD = "your-password";   // ← 実際の値に書き換えて使う
```

**この構成には、実際の値に書き換えたまま誤ってコミットするとパスワードがリポジトリに残る、というリスクがあります。** Gitの履歴は残り続けるため、後からコミットを取り消してもリモートにpush済みであれば漏洩は取り消せません（履歴の書き換えとパスワードのローテーションが必要になります）。

学習用サンプルとしての可読性を優先して現状はこのままとしていますが、**実運用や公開リポジトリでは対処が必要**です。対処方法の例を挙げます。

| 方法 | 概要 | 向いている場面 |
|---|---|---|
| **認証情報を別ヘッダに分離** | `secrets.h` に定義して `#include "secrets.h"` し、`secrets.h` を `.gitignore` に追加。テンプレートとして `secrets.h.example` をコミットしておく | 最も手軽。まずはこれで十分 |
| **NVS / Preferences に保存** | ESP32のNVS領域に認証情報を保存し、コードからは `Preferences` で読み出す | 認証情報をソースから完全に分離したい場合 |
| **WiFiManager 等でプロビジョニング** | 未設定時にM5Stack自身がAPを立て、ブラウザから設定を入力させる | 配布する・複数台に展開する場合 |
| **ビルド時に注入** | PlatformIOの `build_flags` などでコンパイル時にマクロとして渡す | CI/CDに載せる場合 |

いずれの場合も、**一度でも実際の認証情報をコミットしてしまった場合は、履歴からの除去だけでなくWiFiパスワード自体の変更が必要**です。

なお、同じ問題は本サンプルには存在しないものの、MQTTのユーザー名・パスワードやTLSの秘密鍵を導入する際にもそのまま当てはまります。
