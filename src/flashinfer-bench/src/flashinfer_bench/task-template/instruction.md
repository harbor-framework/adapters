Optimize the GPU kernel for `@@DEFINITION@@` on an NVIDIA @@TARGET_GPU@@.

The unchanged FlashInfer-Trace definition (including its mathematical reference)
and workloads are in `/workspace/data`. Produce a FlashInfer-Bench Solution JSON
at `/workspace/solution.json`, with embedded source files and a valid BuildSpec.
Do not use `baseline` as your author. All released workloads for this definition
are evaluated with the pinned upstream evaluator. The score is upstream average
speedup against the released baseline; any failed candidate trace makes it zero.

For the native baseline agent, Harbor invokes the upstream KernelGenerator directly:
its original prompts, random feedback-workload choice, ten-round sequential loop,
and best-passing-candidate selection are unchanged. This file is a packaging
instruction for CLI agents and is not inserted into the native model prompt.
