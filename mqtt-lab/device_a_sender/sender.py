#!/usr/bin/env python3
"""デバイスA: リクエスト送信・応答待受 (Mac / 汎用PC 想定)

使用ライブラリ: paho-mqtt

実行フロー:
  1. ブローカーに接続する
  2. レスポンス用トピックを購読する
  3. リクエスト用トピックに "Hello" を送信する
  4. 応答を受信したら内容を表示して正常終了 (exit code 0)
  5. 送信から10秒以内に応答が無ければエラー表示して異常終了 (exit code 1)
"""

import argparse
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt

# ---- 設定 ------------------------------------------------------------------
# ブローカー(デバイスB)のIPアドレス。実行環境に合わせてここを書き換えるか、
# コマンドライン引数 --host / 環境変数 MQTT_BROKER_HOST で上書きする。
# 優先順位: コマンドライン引数 > 環境変数 > 以下の既定値
BROKER_HOST = "192.168.1.100"
BROKER_PORT = 1883

CLIENT_ID = "device-a"

REQUEST_TOPIC = "mqtt-lab/hello/request"
RESPONSE_TOPIC = "mqtt-lab/hello/response"
QOS = 1

REQUEST_PAYLOAD = "Hello"

# 「送信から」応答を待つ秒数。この10秒だけは仕様通り厳密に扱う。
RESPONSE_TIMEOUT_SEC = 10.0
# 接続〜購読完了〜送信までに許容する秒数 (仕様外の保険)
CONNECT_TIMEOUT_SEC = 10.0

# ---------------------------------------------------------------------------


def resolve_host() -> str:
    """コマンドライン引数 > 環境変数 > 既定値 の優先順位でホストを決定する。"""
    parser = argparse.ArgumentParser(
        description="MQTTでHelloを送信し、応答を待つ (デバイスA)"
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"ブローカーのホスト名/IPアドレス (未指定時: 環境変数 MQTT_BROKER_HOST "
             f"→ {BROKER_HOST})",
    )
    args = parser.parse_args()
    return args.host or os.environ.get("MQTT_BROKER_HOST") or BROKER_HOST


def main() -> int:
    host = resolve_host()

    published = threading.Event()   # 購読完了 → リクエスト送信 まで到達した
    responded = threading.Event()   # 応答を受信した
    state: dict[str, object] = {"payload": None, "error": None}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)

    def on_connect(_client, _userdata, _flags, reason_code, _properties=None):
        if reason_code != 0:
            state["error"] = f"ブローカーへの接続を拒否されました: {reason_code}"
            published.set()
            return
        print(f"ブローカーに接続しました: {host}:{BROKER_PORT}", flush=True)
        # 3. の送信より先に 2. の購読を確実に成立させる。
        # subscribe() は非同期なので、SUBACK を受け取る on_subscribe で送信する。
        _client.subscribe(RESPONSE_TOPIC, qos=QOS)

    def on_subscribe(_client, _userdata, _mid, _reason_codes, _properties=None):
        print(f"購読しました: {RESPONSE_TOPIC} (QoS {QOS})", flush=True)
        _client.publish(REQUEST_TOPIC, REQUEST_PAYLOAD, qos=QOS)
        print(f"送信しました: {REQUEST_TOPIC} <- {REQUEST_PAYLOAD!r} (QoS {QOS})", flush=True)
        published.set()

    def on_message(_client, _userdata, message):
        state["payload"] = message.payload.decode("utf-8", errors="replace")
        responded.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    # 1. ブローカーに接続する
    try:
        client.connect(host, BROKER_PORT, keepalive=60)
    except OSError as exc:
        print(f"エラー: ブローカー {host}:{BROKER_PORT} に接続できません: {exc}",
              file=sys.stderr)
        return 1

    client.loop_start()
    try:
        if not published.wait(CONNECT_TIMEOUT_SEC):
            print(f"エラー: {CONNECT_TIMEOUT_SEC:.0f}秒以内に接続・購読・送信を"
                  f"完了できませんでした。", file=sys.stderr)
            return 1
        if state["error"]:
            print(f"エラー: {state['error']}", file=sys.stderr)
            return 1

        # 5. 送信から10秒以内に応答が来ない場合はタイムアウト
        sent_at = time.monotonic()
        if not responded.wait(RESPONSE_TIMEOUT_SEC):
            elapsed = time.monotonic() - sent_at
            print(
                f"エラー: タイムアウトしました。{RESPONSE_TOPIC} への応答が "
                f"{RESPONSE_TIMEOUT_SEC:.0f}秒以内に届きませんでした "
                f"(待機 {elapsed:.1f}秒)。デバイスCが起動・接続済みか確認してください。",
                file=sys.stderr,
            )
            return 1

        # 4. 応答を受信したら内容を表示して正常終了
        print(f"応答を受信しました: {RESPONSE_TOPIC} -> {state['payload']!r}", flush=True)
        return 0
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
