"""Package Git-visible SOUL source only; never include private runtime or model assets."""
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED_PARTS={'.git','.venv','venv','node_modules','.next','out','build','coverage','data','models','runtime','work','verification-private','__pycache__','.pytest_cache','checkpoints','prepared','exaone'}
FORBIDDEN_SUFFIXES={'.pyc','.log','.db','.sqlite','.sqlite3','.pem','.key','.gguf','.safetensors','.ckpt','.pt','.pth','.onnx','.bin','.exe','.dll','.zip','.pdf'}
FIXTURES={
    'training/data':{'sft_demo.jsonl','preference_demo.jsonl'},
    'eval/data':{'synthetic_demo.jsonl','qwen_smoke_synthetic.jsonl','synthetic_atoms.json'},
    'examples':{'idea.json','calibration_synthetic.json','human_annotation_template.json'},
}

def include(path):
    path=Path(path)
    try:rel=path.relative_to(ROOT)
    except ValueError:return False
    if path.is_symlink() or '..' in rel.parts:return False
    fixture=FIXTURES.get(rel.parent.as_posix())
    if fixture is not None:return path.name in fixture
    if any(part.lower() in EXCLUDED_PARTS for part in rel.parts):return False
    if rel.parts[:2]==('eval','runs'):return False
    if path.name.startswith('.env'):return rel.as_posix()=='.env.example'
    return path.suffix.lower() not in FORBIDDEN_SUFFIXES and not re.search(r'(?i)\.(sqlite3?|db)(?:-|$)',path.name)

def source_files():
    raw=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z'])
    return [ROOT/name for name in sorted(set(raw.decode('utf-8').split('\0'))) if name and include(ROOT/name) and (ROOT/name).is_file()]

if __name__=='__main__':
    target=ROOT.parent/(ROOT.name+'-source.zip')
    paths=source_files()
    if not paths:raise SystemExit('No source files to package.')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in paths:archive.write(path,Path(ROOT.name)/path.relative_to(ROOT))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(paths)
    print(f'{target.name}: {len(paths)} source files, {target.stat().st_size} bytes')
