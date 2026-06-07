import json, urllib.request, urllib.error, time, uuid

BASE = "http://localhost:8080/api/v1"

def req(method, path, token=None, jbody=None, raw=None, ctype=None):
    url = BASE + path
    headers = {}
    data = None
    if jbody is not None:
        data = json.dumps(jbody).encode()
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
        if ctype: headers["Content-Type"] = ctype
    if token: headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, repr(e)

# 1) login
s, b = req("POST", "/auth/token", jbody={"username": "agent", "password": "agent123"})
print("LOGIN:", s, b[:200])
if s != 200:
    raise SystemExit("login failed")
tok = json.loads(b)["access_token"]

# 2) multipart upload
boundary = "----wf" + uuid.uuid4().hex
content = b"AcmeCorp flagship product: the Acme Rocket Pack, priced at $999. We also sell the Nimbus Drone at $499."
parts = []
def field(name, value):
    parts.append(("--"+boundary).encode())
    parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
    parts.append(b"")
    parts.append(value.encode())
field("title", "Product Catalog")
field("category", "sales")
parts.append(("--"+boundary).encode())
parts.append(b'Content-Disposition: form-data; name="file"; filename="catalog.txt"')
parts.append(b"Content-Type: text/plain")
parts.append(b"")
parts.append(content)
parts.append(("--"+boundary+"--").encode())
parts.append(b"")
body = b"\r\n".join(parts)
s, b = req("POST", "/knowledge/upload", token=tok, raw=body,
           ctype="multipart/form-data; boundary="+boundary)
print("UPLOAD:", s, b[:300])
doc_id = None
if s in (200, 201):
    try: doc_id = json.loads(b).get("id")
    except Exception: pass

# 3) poll status
for i in range(20):
    s, b = req("GET", "/knowledge", token=tok)
    try:
        docs = json.loads(b).get("documents", [])
    except Exception:
        docs = []
    target = None
    for d in docs:
        if doc_id and (str(d.get("id")) == str(doc_id)): target = d
    if target is None and docs: target = docs[0]
    st = target.get("embedding_status") if target else "?"
    print(f"  poll {i}: status={st} docs={len(docs)}")
    if st in ("complete", "completed", "failed"): break
    time.sleep(2)

# 4) semantic search
s, b = req("GET", "/knowledge/search?q=what+products+do+we+sell&top_k=3", token=tok)
print("SEARCH:", s, b[:500])
