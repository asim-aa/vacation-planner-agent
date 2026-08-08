# Possible Flight Combinations (from `flights.csv`)

Every real, non-cancelled route in the dataset (161 of 188 total rows are non-cancelled). Use these origin/destination pairs and a budget at or above "Min Price" when testing `experiment/run_experiment.py` to get a real match.

| Origin | Destination | Flights | Min Price | Max Price | Airlines |
|---|---|---|---|---|---|
| BOS (Boston) | MIA (Miami) | 6 | $123.86 | $574.61 | Delta, Southwest |
| BOS (Boston) | PHX (Phoenix) | 6 | $60.10 | $165.41 | Delta, United |
| DEN (Denver) | MCO (Orlando) | 2 | $108.73 | $629.66 | American, Delta |
| DEN (Denver) | MIA (Miami) | 3 | $532.78 | $532.78 | Delta |
| DEN (Denver) | ORD (Chicago (O'Hare)) | 3 | $289.44 | $289.44 | United |
| DEN (Denver) | SFO (San Francisco) | 2 | $121.14 | $142.15 | American |
| DFW (Dallas/Fort Worth) | BOS (Boston) | 3 | $547.01 | $547.01 | Delta |
| DFW (Dallas/Fort Worth) | DEN (Denver) | 4 | $220.25 | $381.16 | American, United |
| DFW (Dallas/Fort Worth) | JFK (New York (JFK)) | 3 | $437.26 | $437.26 | United |
| DFW (Dallas/Fort Worth) | LAX (Los Angeles) | 4 | $96.01 | $130.41 | American, Southwest, United |
| DFW (Dallas/Fort Worth) | MIA (Miami) | 4 | $330.41 | $515.17 | Delta, Southwest |
| DFW (Dallas/Fort Worth) | PHX (Phoenix) | 4 | $171.05 | $563.58 | JetBlue |
| DFW (Dallas/Fort Worth) | SFO (San Francisco) | 1 | $198.81 | $198.81 | Delta |
| JFK (New York (JFK)) | BOS (Boston) | 9 | $419.04 | $595.34 | Delta, JetBlue, United |
| JFK (New York (JFK)) | DEN (Denver) | 2 | $425.43 | $425.43 | Delta |
| JFK (New York (JFK)) | LAX (Los Angeles) | 2 | $375.32 | $524.10 | Delta, United |
| JFK (New York (JFK)) | MIA (Miami) | 3 | $133.42 | $133.42 | JetBlue |
| JFK (New York (JFK)) | ORD (Chicago (O'Hare)) | 1 | $572.76 | $572.76 | American |
| JFK (New York (JFK)) | SFO (San Francisco) | 5 | $183.76 | $543.08 | American, Delta, United |
| LAX (Los Angeles) | BOS (Boston) | 4 | $211.23 | $623.51 | American, Delta, United |
| LAX (Los Angeles) | DEN (Denver) | 1 | $390.87 | $390.87 | Delta |
| LAX (Los Angeles) | MCO (Orlando) | 5 | $50.77 | $550.04 | Delta, United |
| LAX (Los Angeles) | MIA (Miami) | 3 | $161.76 | $161.76 | Delta |
| LAX (Los Angeles) | PHX (Phoenix) | 4 | $54.78 | $322.09 | Delta, JetBlue |
| LAX (Los Angeles) | SFO (San Francisco) | 3 | $467.24 | $622.64 | Delta |
| MCO (Orlando) | DFW (Dallas/Fort Worth) | 3 | $198.12 | $598.74 | Delta, United |
| MCO (Orlando) | JFK (New York (JFK)) | 1 | $571.21 | $571.21 | Southwest |
| MCO (Orlando) | LAX (Los Angeles) | 3 | $550.81 | $550.81 | Delta |
| MCO (Orlando) | MIA (Miami) | 4 | $309.28 | $312.42 | Delta, JetBlue |
| MIA (Miami) | BOS (Boston) | 6 | $59.73 | $432.22 | American, United |
| MIA (Miami) | DFW (Dallas/Fort Worth) | 1 | $570.83 | $570.83 | JetBlue |
| MIA (Miami) | MCO (Orlando) | 1 | $150.36 | $150.36 | Delta |
| MIA (Miami) | ORD (Chicago (O'Hare)) | 4 | $251.57 | $463.66 | American, JetBlue |
| MIA (Miami) | PHX (Phoenix) | 5 | $337.89 | $465.17 | Delta |
| MIA (Miami) | SFO (San Francisco) | 3 | $175.76 | $243.68 | American, Delta |
| ORD (Chicago (O'Hare)) | JFK (New York (JFK)) | 2 | $284.14 | $492.29 | American, Southwest |
| ORD (Chicago (O'Hare)) | MIA (Miami) | 1 | $593.38 | $593.38 | United |
| ORD (Chicago (O'Hare)) | PHX (Phoenix) | 3 | $393.18 | $393.18 | Southwest |
| ORD (Chicago (O'Hare)) | SFO (San Francisco) | 4 | $534.82 | $566.24 | Delta |
| PHX (Phoenix) | DFW (Dallas/Fort Worth) | 7 | $281.33 | $483.54 | American, Delta |
| PHX (Phoenix) | JFK (New York (JFK)) | 1 | $182.30 | $182.30 | American |
| PHX (Phoenix) | LAX (Los Angeles) | 5 | $147.57 | $496.21 | American, Delta |
| PHX (Phoenix) | MIA (Miami) | 3 | $401.85 | $401.85 | Delta |
| PHX (Phoenix) | SFO (San Francisco) | 1 | $258.83 | $258.83 | Delta |
| SFO (San Francisco) | JFK (New York (JFK)) | 3 | $192.51 | $192.51 | Delta |
| SFO (San Francisco) | LAX (Los Angeles) | 8 | $115.82 | $570.66 | Delta, JetBlue, Southwest |
| SFO (San Francisco) | MCO (Orlando) | 1 | $411.75 | $411.75 | American |
| SFO (San Francisco) | MIA (Miami) | 4 | $574.65 | $574.65 | American, Delta |

**Total real routes:** 48  |  **Total non-cancelled flights:** 161  |  **Cancelled (excluded):** 27

## Example commands (run from `vacation-planner-agent-experiment/`, venv already active)

### ✅ 5 that work

All single-quoted, so the shell doesn't touch the `$`. Each demonstrates a different real outcome — found, over-budget, and no-route are all "working correctly," not failures.

```bash
python3 experiment/run_experiment.py 'flying from Boston to Phoenix, budget $200'
```
Finds 6 real flights ($60.10–$165.41).

```bash
python3 experiment/run_experiment.py 'flying from Boston to Miami, budget $100'
```
Correctly reports not possible — cheapest real option is $123.86, so you're $23.86 short.

```bash
python3 experiment/run_experiment.py 'flying from Dallas to Los Angeles, budget $150'
```
Finds 4 real flights, cheapest $96.01.

```bash
python3 experiment/run_experiment.py 'flying from Los Angeles to Orlando, budget $40'
```
Correctly reports not possible — cheapest real option is $50.77, so you're $10.77 short.

```bash
python3 experiment/run_experiment.py 'flying from Chicago to Boston, budget $300'
```
Correctly reports no route exists — ORD → BOS isn't in this dataset at all (check the table above; it's genuinely missing, not a bug).

### ❌ 3 that don't work

All double-quoted with an unescaped `$` — bash/zsh still expands `$` inside double quotes, so the budget silently never reaches the script. The tool used to guess a $500 default when this happened (and that guess could quietly flip a real "not possible" into a wrong "found" — see below); it no longer guesses. Now every one of these refuses to search at all and tells you no budget was found, rather than searching against a number you never typed.

```bash
python3 experiment/run_experiment.py "flying from Boston to Phoenix, budget $200"
```
Budget swallowed → refuses to search, tells you no budget was found.

```bash
python3 experiment/run_experiment.py "flying from Dallas to Los Angeles, budget $150"
```
Same swallowed-budget failure → same refusal.

```bash
python3 experiment/run_experiment.py "flying from Boston to Miami, budget $100"
```
Same failure again — but this is the one that used to matter most: the correct (single-quoted) version of this exact request says "not possible, $23.86 short," and the old $500-default behavior silently flipped that into a wrong "✅ found," since $500 covers the $123.86 flight. That's exactly the bug that motivated removing the default — a swallowed budget shouldn't just risk a warning, it shouldn't be able to change the answer. Now it just refuses instead.
