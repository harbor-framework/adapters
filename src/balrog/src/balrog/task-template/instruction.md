Complete the BabyAI mission in the running game.

Run `balrog observe` to read the original BALROG instructions, mission, current
text observation, and step budget. Then take one action at a time with:

```bash
balrog act "go forward"
```

Available action strings are `turn left`, `turn right`, `go forward`, `pick up`,
`drop`, and `toggle`. Each response includes the resulting observation and whether
the episode has ended. The game enforces its original step budget. There is one
episode and no reset. Stop when `done` is true.

The evaluator uses the original BabyAI success metric and independently replays
the recorded actions. A successful mission scores 1; an unfinished or failed
mission scores 0. Submit your work by interacting with the game, not by writing
an answer or score file.
