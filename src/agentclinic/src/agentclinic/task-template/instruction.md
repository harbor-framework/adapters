{doctor_prompt}

## How the consultation works

The patient and the measurement reader are reached through the `clinic` MCP server. Speak only through its tools:

- `ask_patient(question)`: say one line of dialogue to the patient (a question, or an examination you perform) and receive the patient's reply.
- `request_test(test)`: order a test by name, for example `Chest_X-Ray`; the measurement reader answers with `RESULTS: ...`. Writing `REQUEST TEST: [test]` in `ask_patient` does the same.
- `submit_diagnosis(diagnosis)`: give your final diagnosis and end the consultation. Writing `DIAGNOSIS READY: [diagnosis]` in `ask_patient` does the same.
- `get_status()`: report how many of your 20 turns you have used, whether a turn is still being answered, and the last reply. It does not use a turn.

Every call to `ask_patient`, `request_test` or `submit_diagnosis` uses one of your 20 turns, the diagnosis included. After 20 turns the clinic stops answering, so give your diagnosis by your 20th turn. Only your first diagnosis counts; it is correct if it names the same disease as the patient's actual diagnosis. Messages longer than 1,000 characters are rejected without using a turn. There is nothing to write to disk: the clinic records the consultation.

Without MCP, the same three actions are available over HTTP: `POST http://clinic:8000/api/ask_patient`, `/api/request_test` or `/api/submit_diagnosis` with the JSON body `{"text": "..."}`; the reply comes back as `{"reply": "..."}`.
