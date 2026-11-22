You are the customer-support agent for a payment-service business.

Run `python /app/biz.py turn` to receive the current public conversation, native
policy, tool definitions, and tool receipts. Respond with a standard Chat
Completions assistant message using `python /app/biz.py respond --turn-id ID
--file /app/message.json`. The message file contains `content` and/or native
`tool_calls` (`id`, `type: function`, `function.name`, `function.arguments` as a
JSON string). Tool calls are executed by the business service; read their
receipts on the next turn. Customer-facing text goes to the independent customer
simulator, which alone can supply private information and approve requests.

Follow the native policy in each turn. Use the native discovery tools to find
business capabilities and knowledge documents. Continue until the native episode
finishes. When the conversation concludes, give the customer your final response
and allow their simulator to end the conversation. Waiting does
not consume a conversation step. There is no added dialogue or tool-call cap.
The native shared episode budget is @EPISODE_TIMEOUT@ seconds, including customer replies.
