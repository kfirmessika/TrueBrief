export const meta = {
  name: 'accuracy-matrix',
  description: 'Run TrueBrief per-stage accuracy checks (the Gemini-vs-TrueBrief map) in parallel, then synthesize one scorecard. Optional/heavier than /accuracy-check — fans out one evaluator subagent per pipeline stage.',
  phases: [
    { title: 'Stage checks', detail: 'one accuracy-evaluator per pipeline stage, in parallel' },
    { title: 'Synthesize', detail: 'combine into a single pass/fail scorecard' },
  ],
}

// Pipeline stage → its accuracy test(s). Mirrors the accuracy-eval skill.
const STAGES = [
  { stage: 'dedup',          cmd: '.venv/Scripts/python.exe -m pytest tests/test_neardup.py -q' },
  { stage: 'harvester',      cmd: '.venv/Scripts/python.exe -m pytest tests/test_extractor_fallback.py tests/test_v3_content_quality.py -k harvester -q' },
  { stage: 'arbiter',        cmd: '.venv/Scripts/python.exe -m pytest tests/test_batch_judge.py tests/test_ic1_ic2.py -q' },
  { stage: 'salience',       cmd: '.venv/Scripts/python.exe -m pytest tests/test_salience.py -q' },
  { stage: 'contradiction',  cmd: '.venv/Scripts/python.exe -m pytest tests/test_contradiction.py tests/test_date_guard_sentinel.py -q' },
  { stage: 'state_of_play',  cmd: '.venv/Scripts/python.exe -m pytest tests/test_state_of_play.py -q' },
  { stage: 'briefer',        cmd: '.venv/Scripts/python.exe -m pytest tests/test_briefer.py -q' },
  { stage: 'golden',         cmd: '.venv/Scripts/python.exe -m pytest tests/test_golden_iran_war.py -q' },
]

const VERDICT = {
  type: 'object',
  properties: {
    stage: { type: 'string' },
    passed: { type: 'boolean' },
    summary: { type: 'string', description: 'pytest pass/fail counts; failing test names if any' },
  },
  required: ['stage', 'passed', 'summary'],
}

phase('Stage checks')
const results = (await parallel(STAGES.map(s => () =>
  agent(
    `From the TrueBrief project root, run exactly this command and report the outcome:\n\n    ${s.cmd}\n\n` +
    `Set passed=true ONLY if pytest reports 0 failures and 0 errors. Use stage="${s.stage}". ` +
    `In summary give the pass/fail counts and, on failure, the failing test names — these are real quality regressions, not flakes.`,
    { label: `accuracy:${s.stage}`, phase: 'Stage checks', schema: VERDICT, agentType: 'accuracy-evaluator' }
  )
))).filter(Boolean)

const failed = results.filter(r => !r.passed)
log(`${results.length - failed.length}/${results.length} stages green` + (failed.length ? ` — failing: ${failed.map(r => r.stage).join(', ')}` : ''))

return {
  green: results.length - failed.length,
  total: results.length,
  failedStages: failed.map(r => r.stage),
  detail: results,
}
