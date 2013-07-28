class BootScaling:
    def __init__(self,
                 instance_count_seed=1,
                 pool_workers=0,        # if left at 0, will always match instance_count_seed
                 multiplier=1,
                 bump_up=0,
                 iterations=1):
        self.instance_count_seed = instance_count_seed
        self.pool_workers = pool_workers
        self.multiplier = multiplier
        self.bump_up = bump_up
        self.iterations = iterations
