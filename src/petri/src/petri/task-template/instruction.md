Run `python3 /workspace/chat.py` to see the current messages in the conversation, printed one JSON object per line.

To reply, run `python3 /workspace/chat.py --reply` and write your reply as plain text to its stdin. It then prints the resulting user message.

Continue until `{ "done": true }`.
