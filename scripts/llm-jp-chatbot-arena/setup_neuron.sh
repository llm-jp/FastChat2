#!/bin/bash
source /opt/aws_neuronx_venv_pytorch_2_5_transformers/bin/activate

git clone -b v0.6.x-neuron https://github.com/aws-neuron/upstreaming-to-vllm.git
cd upstreaming-to-vllm
pip install -r requirements-neuron.txt
VLLM_TARGET_DEVICE="neuron" && pip install -e .
