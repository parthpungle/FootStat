"""Shot geometry in the StatsBomb coordinate system.

StatsBomb pitches are 120 x 80 units, with the team in possession always
attacking the goal at x=120. Goalposts sit at y=36 and y=44 (an 8-unit goal
mouth centred on y=40).

Used by the preprocessing script and, later, the predictor, so training and
inference compute features identically.
"""

import numpy as np

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
GOAL_X = 120.0
GOAL_CENTER_Y = 40.0
LEFT_POST_Y = 36.0
RIGHT_POST_Y = 44.0
GOAL_WIDTH = RIGHT_POST_Y - LEFT_POST_Y


def shot_distance(x, y):
    """Euclidean distance from the shot location to the centre of the goal."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return np.hypot(GOAL_X - x, GOAL_CENTER_Y - y)


def shot_angle(x, y):
    """Angle in radians subtended by the two goalposts at the shot location.

    Ranges from 0 (no view of goal) to pi (on the goal line between the posts).
    Equivalent to the angle between the vectors to each post, written in closed
    form so it stays well-defined on the goal line.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    dx = GOAL_X - x
    dy = y - GOAL_CENTER_Y
    half = GOAL_WIDTH / 2
    return np.arctan2(GOAL_WIDTH * dx, dx**2 + dy**2 - half**2)
