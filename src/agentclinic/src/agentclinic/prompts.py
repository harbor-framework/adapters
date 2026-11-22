import re

MAX_INFERENCES = 20
FINAL_NOTICE = "This is the final question. Please provide a diagnosis.\n"
MAX_REACHED = "Maximum inferences reached"
REQUEST_TEST = "REQUEST TEST"
DIAGNOSIS_READY = "DIAGNOSIS READY"
TEMPERATURE = 0.05
MAX_TOKENS = 200
MAX_UTTERANCE_CHARS = 2000


def normalize_response(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def patient_system_prompt(symptoms: object) -> str:
    base = """You are a patient in a clinic who only responds in the form of dialogue. You are being inspected by a doctor who will ask you questions and will perform exams on you in order to understand your disease. Your answer will only be 1-3 sentences in length."""
    tail = "\n\nBelow is all of your information. {}. \n\n Remember, you must not reveal your disease explicitly but may only convey the symptoms you have in the form of dialogue if you are asked.".format(
        symptoms
    )
    return base + tail


def patient_user_prompt(history: str, question: str) -> str:
    return (
        "\nHere is a history of your dialogue: "
        + history
        + "\n Here was the doctor response: "
        + question
        + "Now please continue your dialogue\nPatient: "
    )


def measurement_system_prompt(information: object) -> str:
    base = 'You are an measurement reader who responds with medical test results. Please respond in the format "RESULTS: [results here]"'
    tail = "\n\nBelow is all of the information you have. {}. \n\n If the requested results are not in your data then you can respond with NORMAL READINGS.".format(
        information
    )
    return base + tail


def measurement_user_prompt(history: str, request: str) -> str:
    return "\nHere is a history of the dialogue: " + history + "\n Here was the doctor measurement request: " + request


def doctor_system_prompt(max_infs: int, infs: int, presentation: object) -> str:
    base = 'You are a doctor named Dr. Agent who only responds in the form of dialogue. You are inspecting a patient who you will ask questions in order to understand their disease. You are only allowed to ask {} questions total before you must make a decision. You have asked {} questions so far. You can request test results using the format "REQUEST TEST: [test]". For example, "REQUEST TEST: Chest_X-Ray". Your dialogue will only be 1-3 sentences in length. Once you have decided to make a diagnosis please type "DIAGNOSIS READY: [diagnosis here]"'.format(
        max_infs, infs
    )
    tail = "\n\nBelow is all of the information you have. {}. \n\n Remember, you must discover their disease by asking them questions. You are also able to provide exams.".format(
        presentation
    )
    return base + tail


def doctor_user_prompt(history: str, last_reply: str) -> str:
    return (
        "\nHere is a history of your dialogue: "
        + history
        + "\n Here was the patient response: "
        + last_reply
        + "Now please continue your dialogue\nDoctor: "
    )


def moderator_system_prompt() -> str:
    return "You are responsible for determining if the corrent diagnosis and the doctor diagnosis are the same disease. Please respond only with Yes or No. Nothing else."


def moderator_user_prompt(correct: str, doctor_dialogue: str) -> str:
    return (
        "\nHere is the correct diagnosis: "
        + correct
        + "\n Here was the doctor dialogue: "
        + doctor_dialogue
        + "\nAre these the same?"
    )


def moderator_is_correct(answer: str) -> bool:
    return normalize_response(answer).lower() == "yes"
