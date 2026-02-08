class ModelMonitor:
    """
    Main interface for ModelShift-Lite monitoring.
    """

    def __init__(self, reference_data):
        """
        Initialize monitor with reference baseline data.
        """
        self.reference_data = reference_data
        self.live_data = None
        self.predictions = None

    def update(self, live_data, predictions):
        """
        Update monitor with new live data and predictions.
        """
        self.live_data = live_data
        self.predictions = predictions

    def compute_drift(self):
        """
        Compute drift metrics between reference and live data.
        """
        pass

    def health_score(self):
        """
        Aggregate drift metrics into a model health score.
        """
        pass
