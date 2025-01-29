#!/bin/bash
source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

git clone -b v0.6.x-neuron https://github.com/aws-neuron/upstreaming-to-vllm.git
cd upstreaming-to-vllm

git clone https://github.com/llm-jp/FastChat2.git
git apply FastChat2/scripts/llm-jp-chatbot-arena/vllm_v0.6.0_neuron.patch

pip install -r requirements-neuron.txt
VLLM_TARGET_DEVICE="neuron" && pip install -e .
