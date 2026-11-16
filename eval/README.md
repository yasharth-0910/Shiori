# eval

Dev-time only, never shipped. Runs a pipeline config on a split (`dev` or `test`) and scores it.
Writes `eval/reports/<date>_<config>/report.json` and `report.md`, never overwriting old reports.
Metrics and rules are in `docs/eval_protocol.md`. Iterate on `dev`; run `test` only for milestones.
