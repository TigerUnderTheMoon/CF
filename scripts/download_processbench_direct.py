"""Direct download of ProcessBench data from HuggingFace (bypass datasets library).

Downloads gsm8k.json and math.json from Qwen/ProcessBench and inspects structure.
"""
import json
import urllib.request
from pathlib import Path

BASE_URL = "https://huggingface.co/datasets/Qwen/ProcessBench/resolve/main"
FILES = ["gsm8k.json", "math.json"]
OUT_DIR = Path("outputs/s3_processbench_preview/raw_data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

all_data = []
for fname in FILES:
    url = f"{BASE_URL}/{fname}"
    print(f"Downloading {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "fma-s3-preview"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"  Loaded {len(data)} samples from {fname}")
    (OUT_DIR / fname).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    if data:
        print(f"  Keys: {list(data[0].keys())}")
        sample = data[0]
        print(f"  question: {str(sample.get('question', ''))[:120]}")
        print(f"  is_correct: {sample.get('is_correct')}")
        if "step_labels" in sample:
            print(f"  step_labels (first 5): {sample['step_labels'][:5]}")
            print(f"  n_step_labels: {len(sample['step_labels'])}")
        if "steps" in sample:
            print(f"  n_steps: {len(sample['steps'])}")
            print(f"  first step: {str(sample['steps'][0])[:120]}")
        print()

    # Tag with source
    for row in data:
        row["_source_file"] = fname.replace(".json", "")
    all_data.extend(data)

print(f"Total samples: {len(all_data)}")
(OUT_DIR / "all_processbench.json").write_text(json.dumps(all_data, ensure_ascii=False), encoding="utf-8")
print(f"Saved to {OUT_DIR / 'all_processbench.json'}")
