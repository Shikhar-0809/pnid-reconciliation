# Eval Metrics

Generated at: 2026-07-05T07:34:29.622334+00:00

## Scenario Summary

| Scenario | Tier | Extraction P | Extraction R | Tag Parse Acc | FP Conflicts |
| --- | --- | ---: | ---: | ---: | ---: |
| scenario_001 | T0 | 1.0 | 1.0 | 1.0 | 0 |
| scenario_002 | T1 | 1.0 | 1.0 | 1.0 | 0 |

## Aggregate Metrics

### Extraction

- Precision: 1.0 (tp=14, fp=0, fn=0)
- Recall: 1.0

### Tag Parse

- Accuracy: 1.0 (tp=14, fp=0, fn=0)

### Confidence Calibration

- Review precision: n/a
- Review recall: n/a
- Flagged incorrect: 0
- Flagged correct: 0
- Unflagged incorrect: 0
- Unflagged correct: 14

### Reconciliation By ConflictType

| ConflictType | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| DUPLICATE_TAG | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_DATASHEET | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_IN_INDEX | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_IN_PID | 2 | 0 | 0 | 1.0 | 1.0 |
| TYPE_MISMATCH | 2 | 0 | 0 | 1.0 | 1.0 |
| VALUE_MISMATCH | 2 | 0 | 0 | 1.0 | 1.0 |
