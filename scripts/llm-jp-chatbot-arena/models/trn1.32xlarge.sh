#!/bin/sh
# ssh 10.0.130.6
source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

env NEURON_RT_VISIBLE_CORES="0-31" vllm serve llm-jp/llm-jp-3-172b-instruct3 \
  --tensor-parallel-size 32 \
  --max-num-seqs 8 \
  --max-model-len 4000 \
  --block-size 4000 \
  --port 8000
