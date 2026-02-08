class SQLiteStore:
    """
    Simple SQLite storage interface for drift metrics.
    """

    def __init__(self, db_path="modelshift.db"):
        self.db_path = db_path

    def connect(self):
        pass

    def save_metrics(self, metrics):
        pass
