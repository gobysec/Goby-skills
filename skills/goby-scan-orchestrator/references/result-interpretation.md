# Goby Result Interpretation

Use this order:
1. current status or selected task
2. main findings
3. operational meaning
4. next actions

For task lists:
- identify the selected `taskid`
- state whether it is running, stopped, or completed
- explain task choice when several candidates exist
- label unfinished tasks as partial

For asset results, prioritize host or IP, exposed ports, protocols or services, and products or applications. Summarize patterns before raw details.

For vulnerability results, prioritize affected asset, vulnerability name, useful rule or file name, and whether findings are isolated or widespread. Do not invent severity.

For POC results:
- say whether matches are broad or narrow
- highlight the strongest keyword matches
- suggest narrower filters when the set is too large
- restate the filter in the summary when a filter was used
