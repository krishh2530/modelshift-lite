import pandas as pd


class BaselineWindow:
    """
    Stores and manages reference baseline data
    representing normal model behavior.
    """

    def __init__(self, data: pd.DataFrame):
        self._validate(data)
        self.data = data.copy()
        self.feature_names = list(data.columns)
        self.num_samples = len(data)

    def _validate(self, data):
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Baseline data must be a pandas DataFrame")

        if data.empty:
            raise ValueError("Baseline data cannot be empty")

    def get_data(self) -> pd.DataFrame:
        """
        Returns a copy of baseline data.
        """
        return self.data.copy()

    def summary(self) -> dict:
        """
        Returns basic metadata about the baseline window.
        """
        return {
            "num_samples": self.num_samples,
            "num_features": len(self.feature_names),
            "feature_names": self.feature_names,
        }
