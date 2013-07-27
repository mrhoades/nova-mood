class TestPassSettings:
    def __init__(self,
                 execution_hostname='',
                 test_name='',
                 instance_name='',
                 nova_name='nova_test',
                 instance_count=2,
                 key_name='nova-keys-east',
                 image_name='Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)',
                 flavor_name='standard.xsmall',
                 nova_assign_floating_ip=True,
                 run_rate_limit_buster=False,
                 logger=None,
                 global_lock=None,
                 test_cases=None,
                 test_case_stats=None):
        self.execution_hostname = execution_hostname
        self.test_name = test_name
        self.instance_name = instance_name
        self.nova_name = nova_name
        self.instance_count = instance_count
        self.id = id
        self.key_name = key_name
        self.image_name = image_name
        self.flavor_name = flavor_name
        self.image_object = None
        self.flavor_object = None
        self.nova_assign_floating_ip = nova_assign_floating_ip
        self.run_rate_limit_buster = run_rate_limit_buster
        self.global_lock = global_lock
        self.logger = logger
        self.test_cases = []
        self.test_case_stats = {}

