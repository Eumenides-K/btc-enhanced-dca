"""DCA value multiplication calculation."""


class MultiplierCalculator:
    """DCA value multiplication calculation module."""
    def __init__(
            self,
            max_multiplier: float = 4.0,
            min_multiplier: float = 0.1
    ):
        self.ahr999_dca_line = 1.2
        self.ahr999_bottom_line = 0.45
        self.max_multiplier = max_multiplier
        self.min_multiplier = min_multiplier

        # multiplier = min_multiplier + k * (ahr999_dca_line - ahr999)^2 / ahr999
        # Calibrate k so multiplier(ahr999_bottom_line) == 1.0
        self._k = (
            (1.0 - self.min_multiplier)
            * self.ahr999_bottom_line
            / (self.ahr999_dca_line - self.ahr999_bottom_line) ** 2
        )

    def calculate_daily_investment_multiplier(self, ahr999_value: float):
        """Calculate daily DCA investment multiplier."""
        if ahr999_value <= 0:
            raise ValueError("ahr999_value must be greater than 0")

        if ahr999_value > self.ahr999_dca_line:
            return 0.0

        multiplier = (
            self.min_multiplier
            + self._k * (self.ahr999_dca_line - ahr999_value) ** 2 / ahr999_value
        )
        return min(self.max_multiplier, float(multiplier))


if __name__ == "__main__":
    print(MultiplierCalculator().calculate_daily_investment_multiplier(0.4))
