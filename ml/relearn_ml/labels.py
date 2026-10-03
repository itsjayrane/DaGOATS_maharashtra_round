LABELS = ["CORRECT", "M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE", "M3_PRINT_NOT_RETURN",
          "M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP", "M6_FLOAT_DIVISION",
          "M7_STRING_MUTABLE", "M8_LIST_ALIASING"]
L2I = {l: i for i, l in enumerate(LABELS)}
# Pairs that produce the same wrong output on many inputs; code structure (not output) separates them.
TWINS = [("M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE"), ("M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP")]
TWIN_OF = {}
for a, b in TWINS:
    TWIN_OF[a], TWIN_OF[b] = b, a
def short(label): return label.split("_")[0]
