#!/bin/sh
# ssh 10.0.139.162
source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

env NEURON_RT_VISIBLE_CORES="0-7" vllm serve cyberagent/calm3-22b-chat \
  --tensor-parallel-size 8 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --block-size 4000 \
  --port 8000

env NEURON_RT_VISIBLE_CORES="8-11" vllm serve llm-jp/llm-jp-3-13b-instruct \
  --tensor-parallel-size 4 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --block-size 4000 \
  --port 8001
