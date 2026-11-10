FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Scorer dependencies, pinned to what CAVA@1af23b1 used.
RUN pip install --no-cache-dir \
    "qa-metrics==0.2.32" "nltk==3.9.1" "scikit-learn==1.3.2" "numpy<2.0" scipy \
    "instruction_following_eval @ git+https://github.com/josejg/instruction_following_eval.git@0c495b2f95155e8b10acb919ae283bfb4d5be6e2"

# qa-metrics downloads nltk data at import and PEDANT models at init; bake both in
# (PEDANT models pinned to zli12321/pedant_models@03519c72, last commit 2024-12-16;
# identical to main as of 2026-10-11).
ENV NLTK_DATA=/usr/share/nltk_data
RUN python -c "import nltk; [nltk.download(p, download_dir='/usr/share/nltk_data') for p in ['averaged_perceptron_tagger','punkt','wordnet','omw-1.4','punkt_tab','averaged_perceptron_tagger_eng']]"
RUN QA=$(python -c "import qa_metrics,os;print(os.path.dirname(qa_metrics.__file__))") \
    && mkdir -p $QA/classifier \
    && for m in lr_classifier tf-idf_vectorizer rule_classifier type_classifier; do \
         python -c "import urllib.request,sys; urllib.request.urlretrieve('https://github.com/zli12321/pedant_models/raw/03519c72bb8cf87520dc741554ab3dd68958716d/'+sys.argv[1]+'.pkl', sys.argv[2])" $m $QA/classifier/$m.pkl; \
       done

COPY . /tests/
# scoring/offline.py disables every download path and checks the model sha256s; this
# smoke test fails the build if any nltk resource or model is missing.
RUN cd /tests && python -c "import cava_score as s; \
assert s.score_record('jeopardy', {'prefixed_answer': 'What is Paris?', 'question': 'Capital of France.'}, 'Paris') == (1, 1); \
assert s.score_record('multimodal_instruction_following', {'filename': '0.wav', 'instruction_id': 'length_constraints:number_sentences', 'instruction_prompt': 'x', 'default_kwarg': [{'key': 'num_sentences', 'value': '1'}, {'key': 'relation', 'value': \"'at least'\"}]}, 'One sentence.') == (1, 1)" \
    && chmod 700 /tests
