"""Phase Q -- how accurate must an estimate of available power be?

P3 Arm D showed the identified sets collapse the moment the curtailed share is formed
from an ESTIMATED potential rather than an exact one. Phase Q turns that switch into
a dial. This package holds the measurement of where real potential estimators sit on
that dial (`anchors.py`); the dial itself is run from `src/identification/`, on the
P3 bounds machinery unchanged.
"""
