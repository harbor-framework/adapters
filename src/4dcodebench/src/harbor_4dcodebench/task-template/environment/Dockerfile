# Agent environment for 4DCodeBench case {case_key}.
#
# {agent_image} is the upstream agent image (harness/agent/Dockerfile on top of
# harness/base/Dockerfile at 4DCodeBench commit {upstream_commit}): CUDA 13, Blender 5.2,
# bpy, PyTorch, Taichi, Warp, FFmpeg and the public checker (`python -m checker`). The
# adapter README shows how to build it.
FROM {agent_image}

# What harness/runtime/infer.py mounts read-only for the agent: the rendered task
# context at /task and the case's reference video at /input/reference.mp4. Nothing
# else of the case (reference world, annotation, estimates) is in this image.
COPY task/ /task/
COPY input/reference.mp4 /input/reference.mp4

WORKDIR /workspace
