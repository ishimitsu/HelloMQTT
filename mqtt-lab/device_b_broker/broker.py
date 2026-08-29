#!/usr/bin/env python3
"""デバイスB: MQTTブローカー兼ロガー (Raspberry Pi 4B 想定)

外部の mosquitto 等の別プロセスには依存せず、このPythonプロセス単体で
MQTTブローカーとして動作する。使用ライブラリは amqtt (aMQTT)。

A/C いずれかからメッセージを受信するたびに、受信日時・送信元クライアントID・
トピック名・メッセージ本文を標準出力にログ出力する。
Ctrl+C (SIGINT) で終了するまで常駐する。
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Any

from amqtt.broker import Broker
from amqtt.contexts import BaseContext
from amqtt.plugins.base import BasePlugin

# ---- 設定 ------------------------------------------------------------------

BIND_ADDRESS = "0.0.0.0"
BIND_PORT = 1883  # MQTT標準ポート

# ---------------------------------------------------------------------------


def _now() -> str:
    """ローカルタイムゾーン付きの受信日時文字列を返す。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class MessageLoggerPlugin(BasePlugin[BaseContext]):
    """ブローカーを通過する全メッセージと接続イベントをログ出力するプラグイン。

    amqtt のブローカーイベントを直接フックしているため、MQTTのPUBLISHパケット
    自体には含まれない「送信元クライアントID」を取得できる。
    (mosquitto に `#` で購読するロガーを付ける構成では、これは取得できない)
    """

    async def on_broker_message_received(
        self, *, client_id: str | None = None, message: Any = None, **_kwargs: Any
    ) -> None:
        if message is None:
            return
        try:
            payload = message.data.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            payload = repr(message.data)
        print(
            f"[{_now()}] MESSAGE  from={client_id}  topic={message.topic}  "
            f"qos={message.qos}  payload={payload!r}",
            flush=True,
        )

    async def on_broker_client_connected(
        self, *, client_id: str | None = None, **_kwargs: Any
    ) -> None:
        print(f"[{_now()}] CONNECT     client_id={client_id}", flush=True)

    async def on_broker_client_disconnected(
        self, *, client_id: str | None = None, **_kwargs: Any
    ) -> None:
        print(f"[{_now()}] DISCONNECT  client_id={client_id}", flush=True)

    async def on_broker_client_subscribed(
        self, *, client_id: str | None = None, topic: str | None = None,
        qos: int | None = None, **_kwargs: Any
    ) -> None:
        print(
            f"[{_now()}] SUBSCRIBE   client_id={client_id}  topic={topic}  qos={qos}",
            flush=True,
        )


# `plugins` を明示すると amqtt の既定プラグインは読み込まれなくなるため、
# 匿名接続を許可する AnonymousAuthPlugin も併せて指定する。
BROKER_CONFIG: dict[str, Any] = {
    "listeners": {
        "default": {"type": "tcp", "bind": f"{BIND_ADDRESS}:{BIND_PORT}"},
    },
    "plugins": {
        # 学習用途のため無認証。本番運用ではユーザー認証・TLS化が必要。
        "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True},
        f"{__name__}.MessageLoggerPlugin": {},
    },
}


async def main() -> None:
    broker = Broker(BROKER_CONFIG)

    try:
        await broker.start()
    except Exception as exc:  # 接続失敗時にエラーメッセージを出す程度の最低限の処理
        print(f"ブローカーの起動に失敗しました: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"[{_now()}] ブローカーを起動しました ({BIND_ADDRESS}:{BIND_PORT})", flush=True)
    print("終了するには Ctrl+C を押してください。", flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()

    print(f"\n[{_now()}] シャットダウンしています...", flush=True)
    await broker.shutdown()
    print(f"[{_now()}] ブローカーを停止しました。", flush=True)


if __name__ == "__main__":
    # amqtt 自体のログは抑制し、本プログラムのログだけを見やすくする
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
