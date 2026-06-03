"""Smoke test: voice WS department transfer produces TWO spoken turns.

Logs in, starts a voice session in Reception, opens the voice WS, injects a
text utterance asking for HR, and verifies the server emits a `transfer`
event plus TWO `agent` text frames and TWO `audio` frames (handoff phrase +
HR's real reply).
"""
import asyncio
import base64
import json
import sys

import httpx
import websockets

API = "http://localhost:8080"
WS = "ws://localhost:8080/api/v1/ws/voice"


async def main() -> int:
    async with httpx.AsyncClient(timeout=30) as c:
        tok = (await c.post(f"{API}/api/v1/auth/token",
                            json={"username": "admin", "password": "changeme123"})).json()
        token = tok["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        sess = (await c.post(f"{API}/api/v1/voice/sessions", headers=h,
                             json={"department": "reception"})).json()
        session_id = sess.get("session_id") or sess.get("id")
        print("session_id:", session_id)

    agents, audios, transfer = [], 0, None
    try:
        ws_cm = websockets.connect(f"{WS}/{session_id}", additional_headers=h, max_size=None)
    except TypeError:
        ws_cm = websockets.connect(f"{WS}/{session_id}", extra_headers=h, max_size=None)
    async with ws_cm as ws:
        await ws.send(json.dumps({
            "type": "text",
            "content": "I need to speak to HR about my leave balance",
        }))
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=45)
                m = json.loads(raw)
                t = m.get("type")
                if t == "transfer":
                    transfer = m.get("department")
                    print("TRANSFER ->", transfer)
                elif t == "agent":
                    agents.append(m.get("text", "")[:90])
                    print(f"AGENT[{m.get('department')}]:", m.get("text", "")[:90])
                elif t == "audio":
                    audios += 1
                    n = len(base64.b64decode(m.get("data", "")))
                    print(f"AUDIO #{audios}: {n} bytes ({m.get('provider')})")
                elif t == "error":
                    print("ERROR:", m.get("message"))
                # Stop once we've seen the handoff + new-dept reply (2 audio).
                if audios >= 2 and len(agents) >= 2:
                    break
        except asyncio.TimeoutError:
            print("(timeout waiting for frames)")

    ok = transfer == "hr" and len(agents) >= 2 and audios >= 2
    print("\nRESULT:", "PASS" if ok else "FAIL",
          f"(transfer={transfer}, agents={len(agents)}, audios={audios})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
