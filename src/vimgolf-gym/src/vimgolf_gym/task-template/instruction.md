Vimgolf is a game where you try to transform text using the fewest number of keystrokes in Vim.

Your task is to solve the following Vimgolf challenge with details:

Details:

{{DETAILS}}

The input file wrapped in triple backticks:

```
{{INPUT}}
```

The output file wrapped in triple backticks:

```
{{OUTPUT}}
```

Your keystokes must be less than the length of output file. Do not naively copy and paste the output file. You must use Vim commands to transform the input file into the output file.

Here are some example solutions, for format demostration (all solutions shall be in one line):

iHello World<Esc>:wq<NL>

:%s/abcdef/defabc/g<NL>:wq<NL>

Write your solution to `/app/solution.txt` as a single line. Only the first non-empty line of that file is used. Do not wrap the solution in any marker (like triple backticks) and do not add comments or explanations to the file. If your solution contains multiple steps, concatenate them into one line, optionally using <NL> as separator, depending on the situation.

The input and output files are also available at `/app/input.txt` and `/app/output.txt`. Vim and the `vimgolf` CLI (version 0.5.1) are installed, so you can test a candidate with:

vimgolf local /app/input.txt /app/output.txt "$(head -n 1 /app/solution.txt)"

Your solution is replayed in a fresh Vim (vimgolf's vimrc, restricted mode, no network, no other files), and is accepted when the resulting file matches the output file and the solution has no more keystrokes than the output file has characters.
