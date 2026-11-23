You are the manager of a football club for {years} in-game seasons. This is a long task: one run has several hundred decision stops, and it only ends when the game reports `game_over`.

## Goal

Finish the run with the highest composite score you can. The score rewards league titles, the value you add to the club's net worth, and the value of your squad. Being sacked or going bankrupt ends the run early and discounts the score.

## How to play

The game runs on a separate server. You play it with the `fm` command:

- `fm packet` shows the current decision stop: date, league position, cash, board confidence, your inbox and your notebook.
- `fm tools` lists the 26 tools and their argument schemas.
- `fm call <tool> '<json args>'` calls a tool, for example `fm call get_squad` or `fm call set_tactics '{"formation": "4-3-3", "style": "possession"}'`.
- `fm advance` ends the current stop. The game simulates forward to the next stop and prints its packet.

Read the rulebook at `/app/rules.md` before your first move. It explains the scoring, the board, transfers, contracts, and what information is hidden from you.

## Rules of the task

- The first stop is a squad draft. Call `get_draft_pool`, then `submit_draft`, then advance.
- Time only moves when you call `fm advance`. Keep advancing until a packet contains `"game_over": true`.
- Each stop allows a limited number of query calls and of transfer-negotiation calls. A call over the limit returns an error and does not count.
- Player abilities are shown as ranges from your scouts, never as exact values.
- Only actions sent through `fm` count. There is nothing to submit at the end: the server scores the game as it stands when you stop. A run that is not played to `game_over` is scored as abandoned.
