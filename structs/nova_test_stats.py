from datetime import datetime
from decimal import Decimal


class NovaTestStats:

    def __init__(self,
                 test_name,
                 environ_name,
                 zone,
                 region,
                 execution_host,
                 cloud_account_username,
                 test_pass_id=None,
                 concurrency_count=1,
                 zone_label=None):
        self.test_name = test_name
        self.environ_name = environ_name
        if zone_label is not None:
            self.zone = zone_label
        self.zone_label = zone_label
        self.region = region
        self.execution_host = execution_host
        self.cloud_account_username = cloud_account_username
        self.test_pass_id = test_pass_id
        self.concurrency_count = concurrency_count
        self.time_started = datetime.now()
        self.time_ended = 0
        self.time_total = 0
        self.time_to_active = 0
        self.time_to_ping = 0
        self.time_to_ssh = 0
        self.time_to_deleted = 0
        self.is_active = 0
        self.is_ping_able = 0
        self.is_ssh_able = 0
        self.is_successful = 0
        self.hard_errors_exist = False
        self.hard_error_count = 0
        self.soft_error_count = 0
        self.nova_actions_list = []
        self.rps = 0

    def add_action_stat(self, nova_action, time_started, time_ended, error_type=None, error_text=None):

        action_stat_time_total = (time_ended-time_started).total_seconds()
        stat = self.NovaActionStat(nova_action, time_started, time_ended,
                                   action_stat_time_total, error_type, error_text)
        self.nova_actions_list.append(stat)

        if error_type is not None and error_type != '':

            if 'http 429' in str(error_type).lower() or 'rate-limited' in str(error_type).lower() or 'rate limit' in str(error_type).lower():
                self.soft_error_count += 1
            elif 'http 413' in str(error_type).lower() or 'quota exceeded' in str(error_type).lower():
                self.soft_error_count += 1
            elif 'ssh timeout' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'floating ip attach failed' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'http 500' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'http 404' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'http 400' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'ping timeout' in str(error_type).lower():
                self.hard_error_count += 1
            elif 'delete server timeout' in str(error_type).lower():
                self.soft_error_count += 1
            elif 'address quota exceeded' in str(error_type).lower():
                self.soft_error_count += 1
            else:
                print 'unknown error type in error text: {0}'.format(error_text)
                self.hard_error_count += 1

            if self.hard_error_count > 0:
                self.hard_errors_exist = True

    def ended(self):
        self.time_ended = datetime.now()
        self.time_total = (self.time_ended-self.time_started).total_seconds()
        nova_request_count = len(self.nova_actions_list)
        rps = Decimal(nova_request_count)/Decimal(self.time_total)
        rps = round(rps, 3)
        self.rps = rps

    def now_active(self):
        self.time_to_active = (datetime.now()-self.time_started).total_seconds()
        self.is_active = 1

    def now_pingable(self):
        self.time_to_ping = (datetime.now()-self.time_started).total_seconds()
        self.is_ping_able = 1

    def now_sshable(self):
        self.time_to_ssh = (datetime.now()-self.time_started).total_seconds()
        self.is_ssh_able = 1

    def now_deleted(self):
        self.time_to_deleted = (datetime.now()-self.time_started).total_seconds()

    class NovaActionStat:
        def __init__(self,
                     nova_action,
                     time_started,
                     time_ended,
                     time_total,
                     error_type=None,
                     error_text=None):
            self.nova_action = nova_action
            self.time_started = time_started
            self.time_ended = time_ended
            self.time_total = time_total
            self.error_type = error_type
            self.error_text = error_text
