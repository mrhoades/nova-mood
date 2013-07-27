class Config:
    def __init__(self,
                 nova_auth,
                 test_pass_settings=None,
                 throttle=None,
                 timeouts=None,
                 global_lock=None):
        self.nova_auth = nova_auth
        self.test_pass_settings = test_pass_settings
        self.throttle = throttle
        self.timeouts = timeouts
        self.global_lock = global_lock
