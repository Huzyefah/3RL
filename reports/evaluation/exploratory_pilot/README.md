# Exploratory pilot

This directory preserves version 0 source, scenario-level results and summary output inspected during development. Its final-test seed base was 3000. It lacked the final backlog gate and did not couple provider latency to reduced worker throughput. Only seven pilot test runs met its incident criterion, and its warning rule over-alerted on slowdowns without incidents.

Do not combine its percentages with final version 1.1 results or claim it is an independent holdout. The v1.1 detector and simulator were revised after this inspection; final seed base 9000 was used afterward without further tuning.

The archived source is preserved byte-for-byte at its original relative-root assumption. To reproduce the pilot, copy it as `src/scenarios.py` into a disposable copy of the package and run there; it will overwrite that disposable copy's synthetic outputs. Do not execute the archived file in place or overwrite the main final package. No archive file represents an application implementation.
