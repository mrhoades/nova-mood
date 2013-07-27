import re


class Server:
    def __init__(self,
                 id,
                 name,
                 network='HPCS.PaaS.CIE@hp.com-network',
                 zone='az2',
                 ip_local=None,
                 ip_public=None,
                 ip_floating=None,
                 status='BUILD',
                 key_name='cie-jenkins',
                 image_name='Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)',
                 flavor='standard.xsmall',
                 security_group='matty-secgroup'):
        self.id = id
        self.name = name
        self.network = network
        self.zone = zone
        self.ip_local = ip_local
        self.ip_public = ip_public
        self.ip_floating = ip_floating
        self.status = status
        self.key_name = key_name
        self.image_name = image_name
        self.flavor = flavor
        self.security_group = security_group
        self.fault = None
        self.is_timed_out = False
        self.is_pingable = False
        self.is_sshable = False
        self.created = None
        self.stats_time_to_active = None
        self.stats_time_to_ping = None
        self.stats_time_to_ssh = None
        self.stats_time_to_deleted = None

    def update_ips(self, nova_addresses_string):
        if nova_addresses_string:
            local_addy = re.findall(re.compile("10.\d{1,3}\.\d{1,3}\.\d{1,3}"), str(nova_addresses_string), flags=0)
            public_addy = re.findall(re.compile("15.\d{1,3}\.\d{1,3}\.\d{1,3}"), str(nova_addresses_string), flags=0)
            float_addy = re.findall(re.compile("15.\d{1,3}\.\d{1,3}\.\d{1,3}"), str(nova_addresses_string), flags=0)
            if local_addy:
                self.ip_local = local_addy[0]
            if public_addy:
                self.ip_public = public_addy[0]
            if float_addy:
                self.ip_floating = float_addy[0]

    def update_floating_ip(self, nova_addresses_string):
        if nova_addresses_string:
            float_addy = re.findall(re.compile("15.\d{1,3}\.\d{1,3}\.\d{1,3}"), str(nova_addresses_string), flags=0)
            if float_addy:
                self.ip_floating = float_addy[0]
