# Experiments

## Plain English

One folder per experiment. Each says what drives the dish, which electrode
wiring it assumes, and what it is trying to find out. A run records which
folder it belongs to, so months later a recording says what it was.

## Layout

    experiments/
      electrodes/<name>.json          the dish wiring, shared between experiments
      calibration/<test>/             tests that establish the signal, not use it
      <experiment>/config.json        driver, electrode config, parameters
      <experiment>/README.md          what it tests, in plain English

Calibration tests are named by their path -- `calibration/noise-floor` -- so a
run tagged with one reads as what it is. See `calibration/README.md`.

## config.json

| field | meaning |
|---|---|
| `name` | folder name, repeated so a loose file identifies itself |
| `driver` | `loop` (the model drives the panel) or `stimulus` (a fixed schedule) or `none` (recording only) |
| `electrodes` | a name under `electrodes/` |
| `prompt` | prompt variant from `llm/filters/prompts.md`, for `loop` only |
| `params` | driver arguments |
| `establishes` | what a calibration test settles. Null for experiments that use the signal rather than establish it |
| `preregistered` | where the pre-registration is written, if there is one |

## Runs

`data/run.json` and `data/runs.jsonl` carry `experiment` and `electrodes`
alongside `mode`. Readings and turn logs already carry `run_id`, so every row
joins back to the dish it came from.

Changing the wiring means writing a new file under `electrodes/`, not editing
an existing one. An edited configuration silently reinterprets every past run
that named it.
