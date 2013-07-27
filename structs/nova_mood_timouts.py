class NovaMoodTimeouts:
    def __init__(self,
                 job=60 * 60 * 10,
                 parent_test=60 * 60 * 1,
                 test=60 * 20,
                 cleanup_env_thread=60 * 3,
                 wait_for_active=60 * 3,
                 ping_instance=60 * 3,
                 ssh_instance=60 * 3):
        self.job = job
        self.parent_test = parent_test
        self.test = test
        self.cleanup_env_thread = cleanup_env_thread
        self.wait_for_active = wait_for_active
        self.ping_instance = ping_instance
        self.ssh_instance = ssh_instance