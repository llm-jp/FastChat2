#!/bin/bash
# ssh 10.0.139.235
CUDA_VISIBLE_DEVICES="0,1" ./.local/bin/vllm serve cyberagent/Mistral-Nemo-Japanese-Instruct-2408  \
  --tensor-parallel-size 2 \
  --max-num-seqs 8 \
  --max-model-len 4096 \
  --port 8000

CUDA_VISIBLE_DEVICES="2,3" ./.local/bin/vllm serve microsoft/phi-4 \
  --tensor-parallel-size 2 \
  --max-num-seqs 8 \
  --max-model-len 4096 \
  --port 8001
