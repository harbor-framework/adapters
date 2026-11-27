# ARC-AGI-3: __TITLE__ (`__GAME_ID__`)

You are playing a game. Your goal is to win. Reply with the exact action you want to take. The final action in your reply will be executed next turn. Your entire reply will be carried to the next turn.

Run `/workspace/play.py` using Python 3.

## Output Frame Schema

- `state`: `"NOT_FINISHED"` | `"WIN"` | `"GAME_OVER"`
- `levels_completed`: Levels finished so far
- `win_levels`: Levels needed to win
- `frame`: 64x64 grid (integer colors 0–15)
- `available_actions`: List of accepted action IDs for this game

## Input Action Schema'

- Standard action: `{"id": <action_id>}`
- Reset level: `{"id": 0}`
- Click: `{"id": 6, "data": {"x": <0-63>, "y": <0-63>}}`

## Scoring

The task is scored as solved only if the game's final `state` is `"WIN"`.
