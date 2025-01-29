#!/bin/bash
# git clone https://github.com/llm-jp/FastChat2.git

source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

git clone https://github.com/vllm-project/vllm.git
cd vllm
git checkout v0.6.0
git apply ~/FastChat2/scripts/llm-jp-chatbot-arena/vllm_v0.6.0_neuron.patch
pip install .
pip install ray
cd ..
