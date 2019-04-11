import numpy as np

class averagePriceBinomialTree:

    def __init__(self, num_steps, volatility, time_period, oneOverRho, intereat_rage):
        self.num_steps = num_steps
        self.volatility = volatility
        self.time_period = time_period
        self.oneOverRho = oneOverRho
        self.discount_factor = np.exp(-1 * intereat_rage * self.time_period)

        self.averagePriceTree = np.zeros((self.num_steps + 1, 2 * self.num_steps * oneOverRho))
        self.assetPriceTree = np.zeros((self.num_steps + 1, self.num_steps + 1))
        self.optionPriceTree = np.zeros((self.num_steps + 1, self.num_steps + 1,  2 * self.num_steps * self.oneOverRho))

    def forwardInduction(self):
        self.up_factor = np.exp(self.volatility * np.sqrt(self.time_period))
        rho = 1 / self.oneOverRho

        for i in range(self.num_steps + 1):
            lower_bound = -i
            for j in range(i + 1):
                self.assetPriceTree[i, j] = self.init_price * (self.up_factor ** lower_bound)
                lower_bound += 2

            len_shooting_index = min(2 ** i, i * self.oneOverRho)
            for j in range(2 * len_shooting_index):
                jump = j - len_shooting_index
                self.averagePriceTree[i, j] = self.init_price * (self.up_factor ** (jump * rho))

        for s in range(self.num_steps + 1):
            len_shooting_index = min(2 ** i, i * self.oneOverRho)
            for k in range(len_shooting_index):
                self.optionPriceTree[self.num_steps, s, k] = max(self.averagePriceTree[self.num_steps, k] - self.strike, 0)


    def grid(self, n, k, j, plus): 
        denominator = self.volatility * np.sqrt(self.time_period) / self.oneOverRho
        numerator = (n + 1) *  self.up_factor ** (k / self.oneOverRho) + self.up_factor ** (j + plus)
        numerator = np.log(numerator / (n + 2))

        return numerator / denominator

    def backwardInduction(self):
        delta_y = self.volatility * np.sqrt(self.time_period)/ self.oneOverRho
        proba_up = (1 / self.discount_factor - 1 / self.up_factor) / (self.up_factor - 1 / self.up_factor)

        for n in reversed(range(self.num_steps)):
            len_shooting_index = max(1, min(2 ** n, n * self.oneOverRho))
            lower_bound = -n
            for i in range(n + 1):
                for k in range(2 * len_shooting_index):
                    k_up = self.grid(n, k - len_shooting_index, lower_bound, 1) + len_shooting_index
                    k_down = self.grid(n, k - len_shooting_index, lower_bound, -1) + len_shooting_index

                    k_up_floor = max(int(np.floor(k_up)), 0)
                    k_up_ceil = min(k_up_floor + 1, 2 * len_shooting_index - 1 + 2)

                    # average_price_up = ((n + 1) * self.averagePriceTree[n, k] + self.assetPriceTree[n + 1, i + 1]) / (n + 2)
                    average_price_up = self.init_price * self.up_factor ** ((k_up - len_shooting_index) / self.oneOverRho)
                    factor_interpolation_up = np.log(average_price_up / self.averagePriceTree[n + 1, k_up_floor]) / delta_y

                    option_price_up = factor_interpolation_up * self.optionPriceTree[n + 1, i + 1, k_up_ceil] + \
                        (1 - factor_interpolation_up) * self.optionPriceTree[n + 1, i + 1, k_up_floor]
                    
                    k_down_floor = max(int(np.floor(k_down)), 0)
                    k_down_ceil = min(k_down_floor + 1, 2 * len_shooting_index - 1 + 2)

                    # average_price_down = ((n + 1) * self.averagePriceTree[n, k] + self.assetPriceTree[n + 1, i - 1]) / (n + 2)
                    average_price_down = self.init_price * self.up_factor ** ((k_down - len_shooting_index)  / self.oneOverRho)
                    factor_interpolation_down = np.log(average_price_down / self.averagePriceTree[n + 1, k_down_floor]) / delta_y

                    assert self.averagePriceTree[n + 1, k_down_floor] != 0

                    option_price_down = factor_interpolation_down * self.optionPriceTree[n + 1, i + 1, k_down_ceil] + \
                        (1 - factor_interpolation_down) * self.optionPriceTree[n + 1, i + 1, k_down_floor]

                    self.optionPriceTree[n, i, k] = proba_up * option_price_up + (1 - proba_up) * option_price_down
                    self.optionPriceTree[n, i, k] *= self.discount_factor
                    
                lower_bound -= 2

    def getOptionPrice(self, init_price, strike):
        self.init_price = init_price
        self.strike = strike

        self.forwardInduction()
        self.backwardInduction()

        return self.optionPriceTree[0, 0, 0]


def test_main():
    test_tree = averagePriceBinomialTree(2, 0.1, 0.12, 3, 0.05)
    option_price = test_tree.getOptionPrice(100, 90)
    print(option_price)


if __name__ == "__main__":
    test_main()

