# Housekeeping plans

One plan per state pass, named `<YYYY-MM-DD-HHMM>.md` (local time it was written).
Each plan turns the red rows of `data/state/STATE.md` (`make state-all`) and the open
critic findings (`data/state/critics/`) into ordered fixes, naming the row that shows
each one fixed. The newest file is the current plan; older ones stay as the record.
Start a new one after a fresh `make state-all`, carrying over what is still open.
