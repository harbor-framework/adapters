#!/usr/bin/env bash
# Reference setup for SUPER-Auto task "mist": train MIST (NAT + MIST co-training) on squadqg with bert-base-uncased.
set -euo pipefail
mkdir -p /workspace && cd /workspace

python3 -m venv /workspace/venv
/workspace/venv/bin/pip install -q --upgrade pip==24.0
/workspace/venv/bin/pip install -q torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
/workspace/venv/bin/pip install -q transformers==4.30.2 tokenizers==0.13.3 huggingface_hub==0.36.2 \
  numpy==1.26.4 tensorboardX==2.6.2.2 pycocoevalcap==1.2 tqdm==4.70.1 rouge==1.0.1 gdown==5.2.0

# Repository at the pinned commit
if [ ! -d /workspace/mist ]; then
  git clone -q https://github.com/kongds/mist /workspace/mist
fi
cd /workspace/mist
git checkout -q 082551f1d3476eef17d9fe96e869ba66cfde9bf1

# Patches:
# 1. transformers renamed add_code_sample_docstrings(tokenizer_class=) to processor_class=.
sed -i 's/tokenizer_class=_TOKENIZER_FOR_DOC/processor_class=_TOKENIZER_FOR_DOC/' bert.py
# 2. With --use_glat and no --wandb, train.py references N before assignment (tensorboard + tqdm logging).
sed -i 's/tb_writer.add_scalar(.N., N.item(), step)/tb_writer.add_scalar("N", outputs[-1].item(), step)/' train.py
sed -i '376s/N.item(),/outputs[-1].item(),/' train.py
grep -q 'processor_class=_TOKENIZER_FOR_DOC' bert.py
grep -q 'add_scalar("N", outputs\[-1\].item()' train.py

# squadqg json dataset (Google Drive link from the README); keep the first 10 rows of each split.
mkdir -p /workspace/data
if [ ! -f /workspace/data/squadqg/train.json ]; then
  /workspace/venv/bin/gdown -q 1YR-xohW7UQZNNQG57o34OOM2TiQeY5J8 -O /workspace/data/squadqg.zip
  /workspace/venv/bin/python -c "import zipfile; zipfile.ZipFile('/workspace/data/squadqg.zip').extractall('/workspace/data')"
fi
mkdir -p /workspace/data/squadqg10
for s in train dev test; do
  head -n 10 /workspace/data/squadqg/$s.json > /workspace/data/squadqg10/$s.json
done

# Pre-fetch bert-base-uncased so the run does not depend on download time.
/workspace/venv/bin/python -c "from transformers import BertTokenizer, BertModel; BertTokenizer.from_pretrained('bert-base-uncased'); BertModel.from_pretrained('bert-base-uncased')"

rm -rf /workspace/output
echo "solve.sh done"
