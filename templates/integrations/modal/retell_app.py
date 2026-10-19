"""Template Modal app for a Retell agent. Copy into <client>/integrations/modal/,
rename the app, and edit the two handlers. Deploy with the kit, which uses
the account MODAL_ACCOUNT selects:

    python kit/modalkit.py serve  clients/acme/integrations/modal/retell_app.py --apply   (temporary URL)
    python kit/modalkit.py deploy clients/acme/integrations/modal/retell_app.py --apply   (persistent URL)

Two endpoints:

  webhook   Retell's agent `webhook_url` points here. Receives call_started,
            call_ended, call_analyzed. Verifies x-retell-signature first.
  function  A Retell custom function (tool) points here. Returns JSON the
            agent reads mid-call. Keep it fast: the caller is waiting.

Secrets: create a Modal secret named in SECRET_NAME holding RETELL_API_KEY
(the key of the Retell workspace whose agent calls this app). Create it in
the Modal dashboard or with `modal secret create` typed in your own shell.

Retell signs each request with the workspace API key. Verification follows
docs.retellai.com > "Secure the webhook". Re-read that page before changing
verify_retell(): the signed string must be the raw body Retell sent.
"""
import json
import os

import modal

APP_NAME = "retell-acme"            # rename per client
SECRET_NAME = "retell-acme"         # Modal secret holding RETELL_API_KEY

image = modal.Image.debian_slim().pip_install("fastapi[standard]", "retell-sdk")
app = modal.App(APP_NAME, image=image)


def verify_retell(raw_body: bytes, signature: str) -> bool:
    from retell import Retell
    client = Retell(api_key=os.environ["RETELL_API_KEY"])
    return client.verify(raw_body.decode("utf-8"), api_key=os.environ["RETELL_API_KEY"],
                         signature=signature or "")


@app.function(secrets=[modal.Secret.from_name(SECRET_NAME)])
@modal.fastapi_endpoint(method="POST")
async def webhook(request: "fastapi.Request"):  # noqa: F821
    from fastapi.responses import JSONResponse
    raw = await request.body()
    if not verify_retell(raw, request.headers.get("x-retell-signature")):
        return JSONResponse({"error": "bad signature"}, status_code=401)
    event = json.loads(raw)
    call = event.get("call") or {}
    if event.get("event") == "call_analyzed":
        fields = (call.get("call_analysis") or {}).get("custom_analysis_data") or {}
        # TODO: forward `fields` to the client's system. Log the call_id only:
        # never log names, numbers, or transcripts.
        print(f"call_analyzed {call.get('call_id')}: {sorted(fields)}")
    return JSONResponse({"ok": True})


@app.function(secrets=[modal.Secret.from_name(SECRET_NAME)])
@modal.fastapi_endpoint(method="POST")
async def function(request: "fastapi.Request"):  # noqa: F821
    from fastapi.responses import JSONResponse
    raw = await request.body()
    if not verify_retell(raw, request.headers.get("x-retell-signature")):
        return JSONResponse({"error": "bad signature"}, status_code=401)
    body = json.loads(raw)
    args = body.get("args") or {}
    # TODO: the real lookup. Return a short result the agent can say.
    return JSONResponse({"result": f"received {sorted(args)}"})
