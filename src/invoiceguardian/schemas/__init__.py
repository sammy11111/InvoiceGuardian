"""Two strictly separated schema families: `runtime` (production pipeline
objects) and `evaluation` (answer-key / benchmark objects, mirrors
answer_keys.json). `evaluation` may import `runtime`; `runtime` must never
import `evaluation`.
"""
