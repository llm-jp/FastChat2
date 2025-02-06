#!/bin/sh
# ssh 10.0.138.36
source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

env NEURON_RT_VISIBLE_CORES="0-15" vllm serve tokyotech-llm/Llama-3.1-Swallow-70B-Instruct-v0.3 \
  --tensor-parallel-size 16 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --block-size 4000 \
  --port 8000

env NEURON_RT_VISIBLE_CORES="16-19" vllm serve weblab-GENIAC/Tanuki-8B-dpo-v1.0 \
  --tensor-parallel-size 4 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --block-size 4000 \
  --port 8001
