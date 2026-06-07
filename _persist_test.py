import json, urllib.request, urllib.error, time, uuid, subprocess
B="http://localhost:8080/api/v1"
def call(m,p,tok=None,jb=None,raw=None,ct=None):
    h={}; d=None
    if jb is not None: d=json.dumps(jb).encode(); h["Content-Type"]="application/json"
    elif raw is not None: d=raw; h["Content-Type"]=ct
    if tok: h["Authorization"]="Bearer "+tok
    r=urllib.request.Request(B+p,data=d,headers=h,method=m)
    try:
        with urllib.request.urlopen(r,timeout=90) as x: return x.status,x.read().decode()
    except urllib.error.HTTPError as e: return e.code,e.read().decode()
tok=json.loads(call("POST","/auth/token",jb={"username":"agent","password":"agent123"})[1])["access_token"]
bd="----wf"+uuid.uuid4().hex
content=b"PERSIST-TEST: The Quantum Widget retails for exactly $1234 and is our newest persistence product."
P=[]
def f(n,v):
    P.append(("--"+bd).encode());P.append(f'Content-Disposition: form-data; name="{n}"'.encode());P.append(b"");P.append(v.encode())
f("title","Persist Doc");f("category","sales")
P+= [("--"+bd).encode(),b'Content-Disposition: form-data; name="file"; filename="p.txt"',b"Content-Type: text/plain",b"",content,("--"+bd+"--").encode(),b""]
s,b=call("POST","/knowledge/upload",tok,raw=b"\r\n".join(P),ct="multipart/form-data; boundary="+bd)
print("UPLOAD",s)
for i in range(20):
    docs=json.loads(call("GET","/knowledge",tok)[1]).get("documents",[])
    st=docs[0].get("embedding_status") if docs else "?"
    if st in ("complete","completed","failed"): print("EMBED",st);break
    time.sleep(2)
print("SEARCH-BEFORE", call("GET","/knowledge/search?q=quantum+widget+price&top_k=2",tok)[1][:200])
print("--- recreating chroma ---")
subprocess.run('docker compose up -d --force-recreate chroma',cwd=r"D:\AI Algo\Developments\AI Workforce",shell=True,capture_output=True)
time.sleep(8)
print("SEARCH-AFTER ", call("GET","/knowledge/search?q=quantum+widget+price&top_k=2",tok)[1][:300])
