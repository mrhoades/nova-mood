class NovaAuth:
    def __init__(self,
                 username='',
                 password=None,
                 tenant_name='',
                 project_id='',
                 api_key='',
                 auth_url='https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0',
                 region='region-b.geo-1',
                 auth_ver='2.0',
                 availability_zone='az1'):
        self.username = username
        self.tenant_name = tenant_name
        self.project_id = project_id
        self.password = password
        self.api_key = api_key
        self.auth_url = auth_url
        self.region = region
        self.auth_ver = auth_ver
        self.availability_zone = availability_zone
