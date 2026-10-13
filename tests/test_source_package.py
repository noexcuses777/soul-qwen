import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('soul_package',Path(__file__).resolve().parents[1]/'scripts/package_release.py')
package=importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)

@pytest.mark.parametrize('name',[
    '.env','.env.local','data/sessions.sqlite3','work/check.json','runtime/server.log',
    'models/Qwen.gguf','src/secret.pem','training/prepared/sft.jsonl','training/data/customer.jsonl',
    'eval/data/real_customer.jsonl','eval/runs/scores.json','examples/customer.json',
    'backup.sqlite3-wal','backup.db','src/weights.safetensors','node_modules/a.js','.next/server.js',
])
def test_private_files_are_never_packaged(name):
    assert not package.include(package.ROOT/name)

@pytest.mark.parametrize('name',[
    '.env.example','src/components/PersonaCard.tsx','backend/prompts.py',
    'training/data/sft_demo.jsonl','training/data/preference_demo.jsonl',
    'eval/data/synthetic_demo.jsonl','examples/idea.json','LICENSE',
])
def test_source_and_explicit_synthetic_fixtures_are_allowed(name):
    assert package.include(package.ROOT/name)
