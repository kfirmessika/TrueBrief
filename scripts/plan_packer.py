import os
import re

# --- CONFIGURATION ---
TASK_FILE = "docs/core/TASK_LIST.md"
PLAN_FILE = "docs/core/EXECUTION_PLAN.md"
COMPLEXITY_THRESHOLD = 20 # Strictly follow the original rules
LOOK_AHEAD_LIMIT = 2 # Prevent planning too far into the future

def parse_dependencies():
    deps = {} 
    if not os.path.exists(PLAN_FILE): return deps
    with open(PLAN_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(r'- ([\d\./]+) [→\->]+ ([\d\./]+)', content)
    for targets, blockers in matches:
        for t in targets.split('/'):
            t = t.strip()
            if t not in deps: deps[t] = []
            for b in blockers.split('/'): deps[t].append(b.strip())
    return deps

def parse_master_list():
    tasks = []
    if not os.path.exists(TASK_FILE): return tasks
    with open(TASK_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(r'\| ([\d\.]+) \| ([^\|]+) \| ([^\|]+) \| ([^\|]+) \| ([^\|]+) \| ([^\|]+) \| ([^\|]+) \|', content)
    for m in matches:
        task_id, name, p_model, b_model, u_model, i_model, complexity = [x.strip() for x in m]
        if task_id == "ID": continue 
        c_val = int(complexity)
        tasks.append({"id": task_id, "name": name, "steps": [
            {"action": "PLAN", "model": p_model, "complexity": c_val},
            {"action": "BUILD", "model": b_model, "complexity": c_val},
            {"action": "UNIT", "model": u_model, "complexity": 3},
            {"action": "INTG", "model": i_model, "complexity": 5}
        ]})
    return tasks

def pack_runs(tasks, dependencies):
    finished_tasks = set()
    completed_steps = {t['id']: 0 for t in tasks}
    runs = []
    
    # Track which task is currently the "Active Focus"
    # We move through the task list sequentially
    while any(v < 4 for v in completed_steps.values()):
        current_run = []
        curr_complexity = 0
        run_task_ids = set()
        pref_model = None

        # Determine model by looking at the very first incomplete action in the master list
        first_incomplete_task = None
        for t in tasks:
            if completed_steps[t['id']] < 4:
                first_incomplete_task = t
                break
        
        if not first_incomplete_task: break
        pref_model = first_incomplete_task['steps'][completed_steps[first_incomplete_task['id']]]['model']

        # Packing loop
        packing = True
        while packing:
            # 1. Identify "Ready and Near" Actions
            ready_pool = []
            active_window_count = 0
            for t in tasks:
                sid = completed_steps[t['id']]
                if sid >= 4: continue
                
                # Window logic: Only allow actions from the next few tasks to prevent hallucination
                # (Unless we are already working on them in this run)
                if t['id'] not in run_task_ids:
                    active_window_count += 1
                    if active_window_count > LOOK_AHEAD_LIMIT: break
                
                # Dependency logic
                blockers = dependencies.get(t['id'], [])
                if all(b in finished_tasks for b in blockers):
                    ready_pool.append((t['id'], t['steps'][sid]))

            if not ready_pool: break
            
            packed_in_this_pass = False
            for tid, action in ready_pool:
                if action['model'] != pref_model: continue
                
                # Rule: Model Purity
                # Rule: Complexity Ceiling
                if curr_complexity + action['complexity'] > COMPLEXITY_THRESHOLD: continue
                
                # Rule: Flash Focus (Single Task ID)
                if pref_model == "FLASH" and run_task_ids and tid not in run_task_ids: continue
                
                # Pack it
                current_run.append({"id": tid, "action": action['action'], "name": [tt['name'] for tt in tasks if tt['id']==tid][0]})
                curr_complexity += action['complexity']
                run_task_ids.add(tid)
                completed_steps[tid] += 1
                if completed_steps[tid] == 4: finished_tasks.add(tid)
                
                packed_in_this_pass = True
                break # Re-evaluate ready pool after every pack to respect vertical order
            
            if not packed_in_this_pass: packing = False

        if current_run:
            runs.append({"model": pref_model, "tasks": current_run, "complexity": curr_complexity})

    return runs

def main():
    deps, tasks = parse_dependencies(), parse_master_list()
    runs = pack_runs(tasks, deps)
    
    output = "# 🛰️ TrueBrief Optimized Execution Runs (Vertical Cluster)\n"
    output += "> **Logic:** Vertical Chaining | Look-Ahead Limit = 2 | Model Purity | Flash Focus\n\n"
    for i, run in enumerate(runs):
        output += f"### RUN [ ] {i+1:02d} — Model: {run['model']} (Load: {run['complexity']})\n**Tasks:**\n"
        for t in run['tasks']:
            output += f"- **{t['id']} {t['action']}** — {t['name']}\n"
        output += "---\n"
    
    with open("docs/core/OPTIMIZED_RUNS.md", "w", encoding="utf-8") as f:
        f.write(output)
    print(f"SUCCESS: {len(runs)} runs generated.")

if __name__ == "__main__": main()
