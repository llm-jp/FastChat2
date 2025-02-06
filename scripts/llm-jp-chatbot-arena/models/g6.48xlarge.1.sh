#!/bin/bash
# ssh 10.0.143.131
CUDA_VISIBLE_DEVICES="0,1,2,3" ./.local/bin/vllm serve google/gemma-2-27b-it  \
  --tensor-parallel-size 4 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --port 8000

CUDA_VISIBLE_DEVICES="4,5,6,7" ./.local/bin/vllm serve Qwen/Qwen2.5-14B-Instruct \
  --tensor-parallel-size 4 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --port 8001
