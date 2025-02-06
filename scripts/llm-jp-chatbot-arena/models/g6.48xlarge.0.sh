#!/bin/bash
# ssh 10.0.137.196
./.local/bin/vllm serve Qwen/Qwen2.5-72B-Instruct \
  --tensor-parallel-size 8 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --port 8000
