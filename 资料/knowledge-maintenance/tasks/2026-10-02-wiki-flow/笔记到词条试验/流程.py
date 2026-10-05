import sys,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent
PILOT=BASE.parent/"小知识库"/"MAC01"
FILES=["1.1 神经网络如何“学习”.md","1.2 从一次step到完整训练过程.md","1.3 logit 概率 交叉熵.md","1.4 计算图、链式法则、反向传播.md","1.5 自动微分的pytorch机制.md"]
PLAN=[(0,1,326),(0,327,605),(0,606,745),(1,1,217),(1,218,625),(1,626,867),(2,1,799),(2,800,1226),(3,1,375),(3,376,765),(3,766,965),(4,1,361),(4,362,576),(4,577,758),(4,759,870)]
STATE=BASE/"状态.json"
sha=lambda b:hashlib.sha256(b).hexdigest()
def state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"completed":0,"pending":None,"steps":[]}
def save(s):
    STATE.write_bytes((json.dumps(s,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
def entries():
    folder=BASE/"词条"
    return sorted(folder.glob("*.md")) if folder.exists() else []
def preserved(s):
    for step in s["steps"]:
        n=step["step"]
        for name,digest in step["entries"].items():
            assert sha((BASE/"版本"/f"{n:02}"/name).read_bytes())==digest,("saved version changed",n,name)
    if s["steps"]:
        expected=s["steps"][-1]["entries"]
        actual={p.name:sha(p.read_bytes()) for p in entries()}
        assert actual==expected, "Current entries differ from the previous completed state"
def read_next():
    s=state();assert s["pending"] is None,"Current input is not finished"
    preserved(s)
    n=s["completed"]+1;assert n<=len(PLAN),"All inputs finished"
    k,start,end=PLAN[n-1];source=PILOT/FILES[k]
    raw=source.read_bytes();lines=raw.decode("utf-8-sig").splitlines()
    text="\n".join(lines[start-1:end])+"\n"
    folder=BASE/"输入";folder.mkdir(exist_ok=True);p=folder/f"{n:02}.md"
    assert not p.exists(),"Input already exists"
    p.write_bytes(text.encode("utf-8"))
    s["pending"]={"step":n,"source":FILES[k],"start":start,"end":end,"source_sha256":sha(raw),"input_sha256":sha(p.read_bytes())}
    save(s)
    print(json.dumps(s["pending"],ensure_ascii=False))
    for i,line in enumerate(text.splitlines(),start):
        print(f"{i}: {line}")
def finish():
    s=state();step=s["pending"];assert step is not None
    n=step["step"];assert n==s["completed"]+1
    assert sha((PILOT/step["source"]).read_bytes())==step["source_sha256"],"Source changed"
    assert sha((BASE/"输入"/f"{n:02}.md").read_bytes())==step["input_sha256"],"Input changed"
    assert (BASE/"过程"/f"{n:02}.md").exists(),"Readable decision record is missing"
    for previous in s["steps"]:
        for name,digest in previous["entries"].items():
            assert sha((BASE/"版本"/f'{previous["step"]:02}'/name).read_bytes())==digest
    folder=BASE/"版本"/f"{n:02}";folder.mkdir(parents=True,exist_ok=False)
    hashes={}
    for p in entries():
        raw=p.read_bytes();(folder/p.name).write_bytes(raw);hashes[p.name]=sha(raw)
    step["entries"]=hashes
    s["steps"].append(step);s["completed"]=n;s["pending"]=None;save(s)
    print(json.dumps({"completed":n,"entries":list(hashes),"input_source":step["source"]},ensure_ascii=False))
if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"read":read_next,"finish":finish}[sys.argv[1]]()
