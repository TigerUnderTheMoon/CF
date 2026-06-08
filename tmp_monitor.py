import time, os, json

traces = 'outputs/real_task_v3/smoke_original_traces.jsonl'
results = 'outputs/real_task_v3/smoke_replay_results.jsonl'
report = 'outputs/real_task_v3/smoke_report.json'

def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding='utf-8') as f:
        return sum(1 for l in f if l.strip())

for i in range(120):
    time.sleep(30)
    t = count_lines(traces)
    r = count_lines(results)
    done = os.path.exists(report)
    print(f'[{i*30}s] traces={t}, replay_results={r}, done={done}', flush=True)
    if done:
        rpt = json.load(open(report, encoding='utf-8'))
        status = rpt.get('status', 'unknown')
        print(f'DONE: status={status}', flush=True)
        break
