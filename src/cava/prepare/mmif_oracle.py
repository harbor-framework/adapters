"""Rule-built responses that satisfy CAVA's MultiModalInstructionFollowing instructions.

Covers the instruction types present in the 1000 shipped records; each response is
checked with the pinned IFEval implementation by validate_oracles.py.
"""

from __future__ import annotations

import ast

# One fluent sentence per language code that langdetect classifies correctly.
LANGUAGE_SENTENCES = {
    "ar": "هذه إجابة قصيرة مكتوبة باللغة العربية فقط، وهي تشرح الفكرة بوضوح وبساطة.",
    "bg": "Това е кратък отговор, написан изцяло на български език, който обяснява идеята ясно.",
    "bn": "এটি সম্পূর্ণ বাংলা ভাষায় লেখা একটি ছোট উত্তর, যা বিষয়টি সহজভাবে ব্যাখ্যা করে।",
    "de": "Dies ist eine kurze Antwort, die vollständig auf Deutsch geschrieben ist und die Idee klar erklärt.",
    "en": "This is a short answer written only in English that explains the idea clearly.",
    "el": "Αυτή είναι μια σύντομη απάντηση γραμμένη εξ ολοκλήρου στα ελληνικά, που εξηγεί την ιδέα με σαφήνεια.",
    "es": "Esta es una respuesta breve escrita completamente en español que explica la idea con claridad.",
    "fa": "این یک پاسخ کوتاه است که به طور کامل به زبان فارسی نوشته شده و موضوع را به روشنی توضیح می دهد.",
    "fi": "Tämä on lyhyt vastaus, joka on kirjoitettu kokonaan suomeksi ja selittää asian selkeästi.",
    "fr": "Ceci est une courte réponse écrite entièrement en français qui explique clairement l'idée.",
    "gu": "આ સંપૂર્ણપણે ગુજરાતી ભાષામાં લખાયેલો એક ટૂંકો જવાબ છે, જે વિષયને સરળ રીતે સમજાવે છે.",
    "he": "זוהי תשובה קצרה שנכתבה כולה בעברית ומסבירה את הרעיון בצורה ברורה ופשוטה.",
    "hi": "यह पूरी तरह से हिंदी में लिखा गया एक छोटा उत्तर है, जो विषय को सरलता से समझाता है।",
    "it": "Questa è una breve risposta scritta interamente in italiano che spiega chiaramente l'idea.",
    "ja": "これは日本語だけで書かれた短い回答で、内容をわかりやすく説明しています。",
    "kn": "ಇದು ಸಂಪೂರ್ಣವಾಗಿ ಕನ್ನಡ ಭಾಷೆಯಲ್ಲಿ ಬರೆಯಲಾದ ಒಂದು ಚಿಕ್ಕ ಉತ್ತರ, ಇದು ವಿಷಯವನ್ನು ಸರಳವಾಗಿ ವಿವರಿಸುತ್ತದೆ.",
    "ko": "이것은 완전히 한국어로 작성된 짧은 답변이며, 내용을 명확하게 설명합니다.",
    "ml": "ഇത് പൂർണ്ണമായും മലയാളം ഭാഷയിൽ എഴുതിയ ഒരു ചെറിയ ഉത്തരമാണ്, ഇത് വിഷയം ലളിതമായി വിശദീകരിക്കുന്നു.",
    "mr": "हे संपूर्णपणे मराठी भाषेत लिहिलेले एक छोटे उत्तर आहे, जे विषय सोप्या पद्धतीने समजावून सांगते.",
    "ne": "यो पूर्ण रूपमा नेपाली भाषामा लेखिएको एउटा छोटो उत्तर हो, जसले विषयलाई सरल रूपमा बुझाउँछ।",
    "pa": "ਇਹ ਪੂਰੀ ਤਰ੍ਹਾਂ ਪੰਜਾਬੀ ਭਾਸ਼ਾ ਵਿੱਚ ਲਿਖਿਆ ਇੱਕ ਛੋਟਾ ਜਵਾਬ ਹੈ, ਜੋ ਵਿਸ਼ੇ ਨੂੰ ਸਰਲ ਢੰਗ ਨਾਲ ਸਮਝਾਉਂਦਾ ਹੈ।",
    "pl": "To jest krótka odpowiedź napisana w całości po polsku, która jasno wyjaśnia ten pomysł.",
    "pt": "Esta é uma resposta curta escrita inteiramente em português que explica a ideia com clareza.",
    "ru": "Это короткий ответ, полностью написанный на русском языке, который ясно объясняет идею.",
    "sw": "Hili ni jibu fupi lililoandikwa kwa Kiswahili pekee, linaloeleza wazo hili kwa uwazi na urahisi.",
    "ta": "இது முழுவதும் தமிழ் மொழியில் எழுதப்பட்ட ஒரு சிறிய பதில், இது விஷயத்தை எளிமையாக விளக்குகிறது.",
    "te": "ఇది పూర్తిగా తెలుగు భాషలో రాసిన ఒక చిన్న సమాధానం, ఇది విషయాన్ని సులభంగా వివరిస్తుంది.",
    "th": "นี่คือคำตอบสั้นๆ ที่เขียนเป็นภาษาไทยทั้งหมด ซึ่งอธิบายแนวคิดได้อย่างชัดเจนและเข้าใจง่าย",
    "tr": "Bu, tamamen Türkçe yazılmış ve fikri açık bir şekilde anlatan kısa bir cevaptır.",
    "uk": "Це коротка відповідь, повністю написана українською мовою, яка чітко пояснює ідею.",
    "ur": "یہ مکمل طور پر اردو زبان میں لکھا گیا ایک مختصر جواب ہے جو موضوع کو آسانی سے سمجھاتا ہے۔",
    "vi": "Đây là một câu trả lời ngắn được viết hoàn toàn bằng tiếng Việt và giải thích ý tưởng rõ ràng.",
    "zh": "这是一个完全用中文写成的简短回答，它清楚地解释了这个想法。",
}

NEUTRAL_SENTENCE = "This is a short answer to the question."


def _kwargs(record: dict) -> dict:
    out = {}
    for item in record["default_kwarg"]:
        value = item["value"]
        try:
            value = ast.literal_eval(value)
        except Exception:
            pass
        out[item["key"]] = value
    return out


def build_response(record: dict) -> str:
    kind = record["instruction_id"]
    kw = _kwargs(record)
    if kind == "startend:end_checker":
        return f"{NEUTRAL_SENTENCE} {kw['end_phrase']}"
    if kind == "length_constraints:number_sentences":
        n = int(kw["num_sentences"])
        count = n if kw["relation"] == "at least" else max(1, n - 1)
        return " ".join(f"This is sentence number {i + 1} of the answer." for i in range(count))
    if kind == "length_constraints:number_words":
        n = int(kw["num_words"])
        words = n + 5 if kw["relation"] == "at least" else max(1, min(5, n - 1))
        return " ".join(["answer"] * words) + "."
    if kind == "keywords:forbidden_words":
        forbidden = {w.lower() for w in kw["forbidden_words"]}
        sentence = "Yes, that is right."
        assert not any(w in sentence.lower() for w in forbidden), forbidden
        return sentence
    if kind == "keywords:letter_frequency":
        letter, n = kw["letter"], int(kw["let_frequency"])
        if kw["let_relation"] == "at least":
            return "Okay. " + " ".join([letter * 3] * (n // 3 + 2))
        # less than: avoid the letter entirely
        candidates = ["Yes.", "No.", "Okay.", "Fine.", "Sure."]
        return next(c for c in candidates if letter.lower() not in c.lower())
    if kind == "language:response_language":
        return LANGUAGE_SENTENCES[kw["language"]]
    if kind == "combination:repeat_prompt":
        return f"{kw['prompt_to_repeat']} {NEUTRAL_SENTENCE}"
    raise ValueError(f"no oracle rule for {kind}")
