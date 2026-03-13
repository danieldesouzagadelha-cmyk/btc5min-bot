def create_grid(price):

    grid_range = 0.01   # 1%
    grid_levels = 10

    lower = price * (1 - grid_range)
    upper = price * (1 + grid_range)

    step = (upper - lower) / grid_levels

    grid = [lower + step*i for i in range(grid_levels+1)]

    return grid
