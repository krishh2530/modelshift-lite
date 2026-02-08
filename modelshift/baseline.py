class BaselineWindow:
    """
    Handles reference baseline data for comparison.
    """

    def __init__(self, data):
        self.data = data

    def get_data(self):
        """
        Return baseline data.
        """
        return self.data
