Solve this visual geometry task using the supplied RGB images. Estimate visually; do not implement PnP, homography, or pose solvers. Submit exactly one JSON answer to `/workspace/answer.json` using the task's native units and schema.

${question}

Images, in task order:

${image_manifest}

The JPEG attachments use the original benchmark's transport (longest edge at most 1280). Image dimensions above refer to the original image coordinates. Units: ${units}.

Answer schema: `${answer_schema}`.

Write the answer to `/workspace/answer.json`; the verifier runs after submission and provides no correctness feedback during the task.
