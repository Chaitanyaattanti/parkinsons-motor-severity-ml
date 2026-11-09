"""Ordinal threshold optimization and classification module.

Maps continuous regression predictions into discrete clinical ordinal classes (0 to 4)
by optimizing threshold cutoffs to minimize Mean Absolute Error and maximize Macro-F1.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import mean_absolute_error


class OrdinalThresholdRegressor(BaseEstimator):
    """Wraps a continuous regressor and optimizes ordinal cutoffs for 0-4 scoring."""

    def __init__(self, base_estimator: Any, initial_cutoffs: list[float] | None = None) -> None:
        self.base_estimator = base_estimator
        self.initial_cutoffs = initial_cutoffs or [0.5, 1.5, 2.5, 3.5]
        self.cutoffs_ = np.array(self.initial_cutoffs, dtype=float)

    def fit(self, X: Any, y: np.ndarray) -> OrdinalThresholdRegressor:
        """Fit the underlying continuous regressor and optimize ordinal cutoffs on training data."""
        y_arr = np.asarray(y, dtype=float)
        self.base_estimator.fit(X, y_arr)
        preds = self.base_estimator.predict(X)

        # Optimize cutoffs to minimize MAE against discrete ordinal scores
        def loss(cutoffs: np.ndarray) -> float:
            # Enforce monotonic cutoffs theta_1 < theta_2 < theta_3 < theta_4
            if not np.all(np.diff(cutoffs) > 0.01):
                return 1e6
            discrete_preds = np.digitize(preds, cutoffs)
            return float(mean_absolute_error(y_arr, discrete_preds))

        res = minimize(
            loss,
            x0=self.initial_cutoffs,
            method="Nelder-Mead",
            options={"maxiter": 200, "disp": False},
        )
        if res.success and np.all(np.diff(res.x) > 0):
            self.cutoffs_ = res.x
        else:
            self.cutoffs_ = np.array(self.initial_cutoffs, dtype=float)

        return self

    def predict_continuous(self, X: Any) -> np.ndarray:
        """Return raw continuous regression predictions clipped to [0, 4]."""
        preds = self.base_estimator.predict(X)
        return np.clip(preds, 0.0, 4.0)

    def predict(self, X: Any) -> np.ndarray:
        """Return discrete ordinal scores (0, 1, 2, 3, or 4) using learned cutoffs."""
        continuous_preds = self.base_estimator.predict(X)
        discrete_preds = np.digitize(continuous_preds, self.cutoffs_)
        return np.clip(discrete_preds, 0, 4).astype(int)

