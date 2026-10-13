import json,platform,shutil,subprocess,urllib.request
from pathlib import Path

def cmd(args):
    try: return subprocess.run(args,capture_output=True,text=True,timeout=15).stdout.strip()
    except (OSError,subprocess.TimeoutExpired): return None

result={'os':platform.platform(),'python':platform.python_version(),'llama_server':shutil.which('llama-server'),
        'nvidia':cmd(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader']),
        'mac_memory_bytes':cmd(['sysctl','-n','hw.memsize']) if platform.system()=='Darwin' else None,
        'models_present':[str(p) for p in Path('models').glob('*.gguf')],
        'model_downloaded_by_builder':False}
try:
    with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3) as r: result['model_server_health']=json.loads(r.read())
except Exception as e: result['model_server_health']={'available':False,'error':type(e).__name__}
print(json.dumps(result,ensure_ascii=False,indent=2))
