class FragmentAPIError(Exception):
    """Raised when the Fragment API returns an error response."""

    def __init__(self, message):
        self.message = str(message)

        super().__init__(self.message)

    def __str__(self):
        return self.message
