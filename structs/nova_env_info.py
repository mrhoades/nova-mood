class NovaTestInfo:
    def __init__(self,
                 env_name='bravo',
                 execution_hostname='',
                 lock=None,
                 test_name='',
                 instance_name='',
                 nova_name='nova_test',
                 instance_count=2,
                 username='',
                 password=None,
                 tenant_name='',
                 project_id='',
                 api_key=None,
                 auth_url='https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0',
                 region='region-b.geo-1',
                 auth_ver='2.0',
                 key_name='',
                 image='Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)',
                 flavor='standard.medium',
                 availability_zone='az1',
                 security_group='perf-metrics',
                 action_sleep_interval=.6,
                 nova_assign_floating_ip=True,
                 cleanup_orphaned_floating_ips=False,
                 run_rate_limit_buster=False,
                 logger=None,
                 timeout_minutes=30,
                 nova_request_timeout=60,
                 global_lock=None,
                 global_dict=None,
                 test_cases=None,
                 test_case_stats=None):
        self.env_name = env_name
        self.execution_hostname = execution_hostname
        self.lock = lock
        self.test_name = test_name
        self.instance_name = instance_name
        self.nova_name = nova_name
        self.instance_count = instance_count
        self.username = username
        self.tenant_name = tenant_name
        self.project_id = project_id
        self.password = password
        self.api_key = api_key
        self.id = id
        self.auth_url = auth_url
        self.region = region
        self.auth_ver = auth_ver
        self.key_name = key_name
        self.image_name = image
        self.flavor_name = flavor
        self.image_object = None
        self.flavor_object = None
        self.availability_zone = availability_zone
        self.security_group = security_group
        self.action_sleep_interval = action_sleep_interval
        self.nova_assign_floating_ip = nova_assign_floating_ip
        self.cleanup_orphaned_floating_ips = cleanup_orphaned_floating_ips
        self.run_rate_limit_buster = run_rate_limit_buster
        self.timeout_minutes = timeout_minutes
        self.global_lock = global_lock
        self.global_dict = global_dict
        self.logger = logger
        self.is_timed_out = False
        self.is_pingable = False
        self.is_sshable = False
        self.created = None
        self.stats_time_to_active = None
        self.stats_time_to_ping = None
        self.stats_time_to_ssh = None
        self.stats_time_to_deleted = None
        self.test_cases = []
        self.test_case_stats = {}

