#!/bin/bash
set -euo pipefail
mkdir -p /workspace && cd /workspace

python3 -m venv /workspace/venv
/workspace/venv/bin/pip install -q torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu
/workspace/venv/bin/pip install -q numpy==1.23.5 scikit-learn==1.2.2 transformers==4.30.2 \
  tqdm==4.66.1 tensorboardX==2.6.2.2

if [ ! -d open_contextual_link_pred ]; then
  git clone https://github.com/mjhosseini/open_contextual_link_pred.git
fi
cd open_contextual_link_pred
git checkout a716995071b421abfff8f23cb7278bba2c364a9b

# Data (scripts/data.sh uses an outdated Google Drive confirm flow). ~2 GB archive;
# keep typed_rels + NS_epair_split, and only the first 1000 triple-mention lines of
# the 7.3 GB news_bert_input.json.
curl -fsSL "https://drive.usercontent.google.com/download?id=1d93CTsJ9OG0I68fHHWvX8iVkSefCmkyq&export=download&confirm=t" -o /workspace/data.tar.gz
/workspace/venv/bin/python - <<'EOF'
import os, tarfile
N = 1000
with tarfile.open("/workspace/data.tar.gz", "r|gz") as tf:
    for m in tf:
        name = m.name
        base = os.path.basename(name)
        if not name.startswith("data/") or base.startswith("._") or base == ".DS_Store":
            continue
        if m.isdir():
            os.makedirs(name, exist_ok=True); continue
        if not m.isfile():
            continue
        os.makedirs(os.path.dirname(name), exist_ok=True)
        f = tf.extractfile(m)
        with open(name, "wb") as out:
            if name == "data/news_bert_input.json":
                for i, line in enumerate(f):
                    if i >= N: break
                    out.write(line)
            else:
                out.write(f.read())
EOF
rm -f /workspace/data.tar.gz
test -s data/news_bert_input.json
test -d data/typed_rels && test -f data/NS_epair_split/train.txt

# Pre-fetch bert-base-uncased (public) so the run does not depend on download timing.
/workspace/venv/bin/python -c "from transformers import BertTokenizer, BertConfig, BertModel; BertTokenizer.from_pretrained('bert-base-uncased'); BertConfig.from_pretrained('bert-base-uncased'); BertModel.from_pretrained('bert-base-uncased')"
echo "solve.sh done"
