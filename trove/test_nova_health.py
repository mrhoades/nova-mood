import testtools
import time
import logging
import telnetlib
from novaclient.v1_1 import client
import re
import os
import StringIO
import urllib2
import subprocess
import ssh
from nose.tools import nottest
from datetime import datetime
import functools
import select

logging.basicConfig(format='%(levelname)s\t%(name)s\t%(message)s')
logger = logging.getLogger('nova_health_tests')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
logger.addHandler(ch)
MINUTE = 60


class PollTimeout(Exception):
    def __init__(self, message, previous_result=None):
        self.message = message
        self.previous_result = previous_result

    def __str__(self):
        return repr(self.value)


def poll_until(retriever, condition=lambda value: value,
               sleep_time=1, time_out=5 * MINUTE):
    """Retrieves object until it passes condition, then returns it.

    If time_out_limit is passed in, PollTimeOut will be raised once that
    amount of time is eclipsed.

    """
    start_time = time.time()

    obj = retriever()
    while not condition(obj):
        time.sleep(sleep_time)
        if time_out is not None and time.time() > start_time + time_out:
            raise PollTimeout("Timeout!", obj)
        obj = retriever()
    return obj


def check_for_exception(f, *args, **kwargs):
    try:
        f(*args, **kwargs)
        return True
    except:
        return False


def execute_ssh_command(ssh_client, command):
    _, stdout, stderr = ssh_client.exec_command(command)
    while not stdout.channel.exit_status_ready():
        time.sleep(1)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        logger.info("WARNING: Exit status is " + str(exit_status))
        logger.info(stderr.readlines())
    return stdout.readlines()


def check_quota_usages(fn):
    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        logger.info("Limit before test:")
        limits = self.nova.limits.get()
        orig_instance_used = None
        for limit in limits.absolute:
            if limit.name == 'totalInstancesUsed':
                logger.info('%s: %s', limit.name, limit.value)
                orig_instance_used = limit.value
                break
        fn(self, *args, **kwargs)
        logger.info("Limit after test: ")
        limits = self.nova.limits.get()
        for limit in limits.absolute:
            if limit.name == 'totalInstancesUsed':
                logger.info('%s: %s', limit.name, limit.value)
                self.assertEquals(orig_instance_used + 1, limit.value)
    return wrapped


class Nova_health_tests(testtools.TestCase):

    def setUp(self):
        super(Nova_health_tests, self).setUp()

        username = os.environ['OS_USERNAME']
        password = os.environ['OS_PASSWORD']
        tenant = os.environ['OS_TENANT_NAME']
        auth_url = os.environ['OS_AUTH_URL']
        cacert = os.getenv('OS_CACERT', False)
        region = os.getenv('OS_REGION_NAME', '')
        self.insecure = True if os.getenv('INSECURE', 'False').lower() == \
                             'true' \
            else False
        self.availability_zone = os.getenv('AVAILABILITY_ZONE', '')
        self.network_label = os.environ['NETWORK_LABEL']
        self.image = os.environ['DEFAULT_IMAGE']
        self.flavor = os.environ['DEFAULT_FLAVOR']
        self.flavor_2 = os.environ['DEFAULT_FLAVOR_2']
        self.non_eph_flavor = os.environ['NON_EPHEMERAL_FLAVOR']
        self.volume_enable = True if os.getenv('ENABLE_VOLUME',
                                               'False').lower() == 'true' \
            else False
        build_number = os.environ['BUILD_NUMBER']
        date = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S-%f")
        self.INSTANCE_NAME = 'nova_test_' + build_number + '_' + date
        self.VOLUME_NAME = 'volume_test_' + build_number + '_' + date
        self.SECGROUP_NAME = 'secgroup_static'
        self.IMAGE_NAME = 'image_test_' + build_number + '_' + date
        self.KEY_NAME = 'key_test' + '_' + build_number + '_' + date
        self.KEY_FILE_NAME = '/tmp/' + self.KEY_NAME
        self.skip_cleanup = False

        self.nova = client.Client(username=username,
                                  api_key=password,
                                  project_id=tenant,
                                  auth_url=auth_url,
                                  service_type="compute",
                                  region_name=region,
                                  insecure=self.insecure,
                                  cacert=cacert)

        if self.volume_enable:
            self.cinder = client.Client(username=username,
                                        api_key=password,
                                        project_id=tenant,
                                        auth_url=auth_url,
                                        service_type="volume")

        self.addOnException(self.disable_cleanup)
        self.cleanup()

    def disable_cleanup(self, exc_info):
        enable_skip_cleanup = os.getenv('ENABLE_SKIP_CLEANUP', 'False')
        if enable_skip_cleanup.lower() == 'true':
            self.skip_cleanup = True

    def tearDown(self):
        super(Nova_health_tests, self).tearDown()
        self.cleanup()

    def test_create_image(self):
        logger.info("-----------------------------------------------")
        logger.info("Starting create image test")
        logger.info("-----------------------------------------------")
        # Download image
        logger.info("Downloading image...")
        image_url = 'https://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-i386-disk.img'
        image = urllib2.urlopen(image_url)
        cmd = ['glance', 'image-create', '--name', self.IMAGE_NAME,
               '--disk-format=raw', '--container-format=bare']
        if self.insecure:
            cmd.insert(1, '--insecure')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=image)

        logger.info("Uploading image to glance...")
        out, err = p.communicate()
        image.close()
        logger.info(out)

        if p.returncode:
            logger.info(err)
            self.fail()

        test_image = [image.name for image in self.nova.images.list()
                      if image.name == self.IMAGE_NAME]

        self.assertTrue(test_image)

    #@check_quota_usages
    def test_resize_flavor(self):
        logger.info("-----------------------------------------------")
        logger.info("Starting resize flavor test")
        logger.info("-----------------------------------------------")

        # Add keypair
        logger.info("Adding new pub key")
        keypair = self.nova.keypairs.create(self.KEY_NAME)
        f = open(self.KEY_FILE_NAME, 'w')
        f.write(keypair.private_key)
        f.close()

        # create sec group + rule
        logger.info("Creating new security group + rules")
        secgroup = self.nova.security_groups.create(self.SECGROUP_NAME,
                                                    'test_boot_with_ephemeral')
        self.nova.security_group_rules.create(secgroup.id, 'tcp', 22, 22,
                                              '0.0.0.0/0')

        # boot instance
        logger.info("Booting new instance: %s", self.INSTANCE_NAME)
        small_flavor = self.nova.flavors.find(name=self.flavor)
        medium_flavor = self.nova.flavors.find(name=self.flavor_2)

        image = self.nova.images.find(name=self.image)
        server_id = self.nova.servers.create(self.INSTANCE_NAME,
                                             image=image,
                                             flavor=small_flavor,
                                             key_name=self.KEY_NAME,
                                             security_groups=[secgroup.name],
                                             availability_zone=self.availability_zone).id
        logger.info("Instance %s is building",  server_id)

        newserver = None
        try:
            newserver = poll_until(lambda: self.nova.servers.get(server_id),
                                   lambda inst: inst.status != 'BUILD',
                                   sleep_time=5)
        except PollTimeout as e:
            newserver = e.previous_result
            error_message = 'Instance is stuck in BUILD.\n' \
                            'Instance ID = ' + server_id + '\n'
            if newserver is not None:
                error_message = error_message + 'Host ID = ' + newserver.hostId + '\n'

            self.fail(error_message)
        finally:
            if newserver is not None:
                logger.info(vars(newserver))

        self.assertEquals('ACTIVE', newserver.status, 'The instance %(id)s is in %(status)s' % {'id': server_id, 'status': newserver.status})
        logger.info("Instance %s is active",  server_id)

        # sleep 10 seconds for instance to be ready (ssh server)
        time.sleep(10)

        # SSH into the instance
        logger.info("Network label for instance %s: %s", server_id, newserver.networks)
        network = newserver.networks[self.network_label][-1]
        logger.info('SSHing to %s', network)
        client = ssh.SSHClient()
        client.load_host_keys('/dev/null')
        client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        try:
            poll_until(lambda: check_for_exception(client.connect,
                                                   network,
                                                   username='ubuntu',
                                                   key_filename=self
                                                   .KEY_FILE_NAME),
                       lambda result: result,
                       sleep_time=5,
                       time_out=10 * MINUTE)

            # Create new file in the instance
            logger.info("Creating new file, test_file, in root partition of the instance...")
            execute_ssh_command(client, "python -c \"import os; import datetime; f = open('/home/ubuntu/test_file','w'); f.write(str(datetime.datetime.now()) + '\\n') ; f.flush(); os.fsync(f.fileno()); f.close()\"")
            result = execute_ssh_command(client, 'ls')
            logger.info(result)
            file_content_before_resize_root = execute_ssh_command(client, "cat test_file")
            logger.info("Content of test_file: " + str(file_content_before_resize_root))
            self.assertTrue('test_file\n' in result, 'Newly create file in root partition, test_file, not found')

            logger.info("Creating new file, test_file_eph, in the ephemeral partition of the instance...")
            execute_ssh_command(client, "sudo python -c \"import os; import datetime; f = open('/mnt/test_file_eph','w'); f.write(str(datetime.datetime.now()) + '\\n') ; f.flush(); os.fsync(f.fileno()); f.close()\"")
            result = execute_ssh_command(client, 'ls /mnt')
            logger.info(result)
            file_content_before_resize_eph = execute_ssh_command(client, "cat /mnt/test_file_eph")
            logger.info("Content of test_file_eph: " + str(file_content_before_resize_eph))
            self.assertTrue('test_file_eph\n' in result, 'Newly create file in ephemeral partition, test_file_eph, not found')
        except PollTimeout:
            error_message = 'Unable to SSH to ' + network + '\n' \
                            'Instance ID = ' + newserver.id + '\n' \
                            'Host ID = ' + newserver.hostId + '\n' \
                            'Status = ' + newserver.status + '\n' \
                            'Network = ' + str(newserver.networks) + '\n'
            self.fail(error_message)
        finally:
            client.close()

        self.nova.servers.resize(newserver.id, medium_flavor)

        logger.info("Resizing instance %s",  server_id)
        resized_server = None
        try:
            resized_server = poll_until(lambda: self.nova.servers.get(server_id),
                                        lambda inst: inst.status != 'BUILD' and
                                        inst.status != 'RESIZE',
                                        sleep_time=10)
            self.assertEquals('VERIFY_RESIZE', resized_server.status, 'The instance %(id)s is in %(status)s' % {'id': resized_server.id, 'status': resized_server.status})
        except PollTimeout as e:
            resized_server = e.previous_result
            error_message = 'Instance is stuck in RESIZE.\n' \
                            'Instance ID = ' + server_id + '\n'
            if resized_server is not None:
                error_message = error_message + 'Host ID = ' + resized_server.hostId + '\n' \
                                                'Status = ' + resized_server.status + '\n' \
                                                'Network = ' + str(resized_server.networks) + '\n'
            self.fail(error_message)
        finally:
            if resized_server is not None:
                logger.info(vars(resized_server))

        self.nova.servers.confirm_resize(newserver.id)
        try:
            resized_server = poll_until(lambda: self.nova.servers.get(server_id),
                                        lambda inst: inst.status != 'BUILD' and
                                        inst.status != 'VERIFY_RESIZE', sleep_time=5)
            self.assertEquals('ACTIVE', resized_server.status, 'The instance %(id)s is in %(status)s' % {'id': resized_server.id, 'status': resized_server.status})
        except PollTimeout as e:

            resized_server = e.previous_result
            error_message = 'Instance is never became ACTIVE after issuing a confirm_resize.\n' \
                            'Instance ID = ' + server_id + '\n'
            if resized_server is not None:
                error_message = error_message + 'Host ID = ' + resized_server.hostId + '\n' \
                                                'Status = ' + resized_server.status + '\n' \
                                                'Network = ' + str(resized_server.networks) + '\n'
            self.fail(error_message)

        self.assertEquals(medium_flavor.id, resized_server.flavor['id'], 'Flavor on resized instance do not match specified flavor')

        logger.info("Network label for instance %s: %s", server_id, newserver.networks)
        network = newserver.networks[self.network_label][-1]
        # sleep 10 seconds while ssh server is starting
        time.sleep(10)

        logger.info('SSHing to %s', network)
        client = ssh.SSHClient()
        client.load_host_keys('/dev/null')
        client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        try:
            poll_until(lambda: check_for_exception(client.connect,
                                                   network,
                                                   username='ubuntu',
                                                   key_filename=self
                                                   .KEY_FILE_NAME),
                       lambda result: result,
                       sleep_time=5,
                       time_out=10 * MINUTE)

            # Testing if created file exists
            logger.info("Verifying test_file exist in root partition of the resized instance...")
            result = execute_ssh_command(client, 'ls')
            logger.info(result)
            file_content_after_resize_root = execute_ssh_command(client, "cat test_file")
            logger.info("Content of test_file: " + str(file_content_after_resize_root))
            self.assertTrue('test_file\n' in result, 'Test file that was created in the root partition before resize is not found after resize')
            self.assertEquals(file_content_before_resize_root[0], file_content_after_resize_root[0], 'Content in files for data stored in ephemeral partition do not match')
            logger.info("Verifying test_file exist in ephemeral partition of the resized instance...")
            result = execute_ssh_command(client, 'sudo ls /mnt')
            logger.info(result)
            file_content_after_resize_eph = execute_ssh_command(client, "cat /mnt/test_file_eph")
            logger.info("Content of test_file_eph: " + str(file_content_after_resize_eph))
            self.assertTrue('test_file_eph\n' in result, 'Test file that was created in the ephemeral partition before resize is not found after resize')
            self.assertEquals(file_content_before_resize_eph[0], file_content_after_resize_eph[0], 'Content in files for data stored in ephemeral partition do not match')

            # Test outbound connectivity
            logger.info("Pinging google.com...")
            exit_status = 0
            for x in range(0, 5):
                _, stdout, stderr = client.exec_command('ping google.com -c 1')

                while not stdout.channel.exit_status_ready():
                    if stdout.channel.recv_ready():
                        rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                        if len(rl) > 0:
                            # Print data from stdout
                            logger.info(stdout.channel.recv(1024))
                    if stderr.channel.recv_stderr_ready():
                        rl, wl, xl = select.select([stderr.channel], [], [], 0.0)
                        if len(rl) > 0:
                            # Print data from stderr
                            logger.error(stderr.channel.recv_stderr(1024))
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    break
                else:
                    # sleep for 5 secs to allow network to be ready
                    time.sleep(5)
            self.assertEquals(0, exit_status, 'Ping to google.com failed!')
        except PollTimeout:
            error_message = 'Unable to SSH to ' + network + '\n' \
                            'Instance ID = ' + resized_server.id + '\n' \
                            'Host ID = ' + resized_server.hostId + '\n' \
                            'Status = ' + resized_server.status + '\n' \
                            'Network = ' + str(resized_server.networks) + '\n'
            self.fail(error_message)
        finally:
            client.close()


    @nottest
    def test_boot_with_volume(self):
        logger.info("-----------------------------------------------")
        logger.info("Starting boot instance with volume test")
        logger.info("-----------------------------------------------")

        # Add keypair
        logger.info("Adding new pub key")
        keypair = self.nova.keypairs.create(self.KEY_NAME)
        f = open(self.KEY_FILE_NAME, 'w')
        f.write(keypair.private_key)
        f.close()

        # create sec group + rule
        logger.info("Creating new security group + rules")
        secgroup = self.nova.security_groups.create(self.SECGROUP_NAME,
                                                    'test_boot_with_volume')
        self.nova.security_group_rules.create(secgroup.id, 'tcp', 22, 22,
                                              '0.0.0.0/0')

        # create volume
        logger.info("Creating new volume")
        volume = self.cinder.volumes.create(1, display_name=self.VOLUME_NAME)
        logger.info("Volume created: " + volume.id)
        bdm = {'/dev/vdb': '{0}:::0'.format(volume.id)}

        # boot instance
        logger.info("Booting new instance: %s", self.INSTANCE_NAME)
        flavor = self.nova.flavors.find(name=self.non_eph_flavor)
        image = self.nova.images.find(name=self.image)
        server_id = self.nova.servers.create(self.INSTANCE_NAME,
                                             image=image,
                                             block_device_mapping=bdm,
                                             key_name=self.KEY_NAME,
                                             security_groups=[secgroup.name],
                                             flavor=flavor,
                                             availability_zone=self.availability_zone).id

        logger.info("Instance %s is building",  server_id)
        newserver = poll_until(lambda: self.nova.servers.get(server_id),
                               lambda inst: inst.status != 'BUILD',
                               sleep_time=5)
        self.assertEquals('ACTIVE', newserver.status)
        logger.info("Instance %s is active",  server_id)
        logger.info(vars(newserver))

        time.sleep(10) # sleep 10 seconds while ssh server is starting
        client = ssh.SSHClient()
        client.load_host_keys('/dev/null')
        client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        logger.info("Network label for instance %s: %s", server_id, newserver.networks)
        network = newserver.networks[self.network_label][-1]
        logger.info('SSHing to %s', network)
        poll_until(lambda: check_for_exception(client.connect,
                                               network,
                                               username='ubuntu',
                                               key_filename=self
                                               .KEY_FILE_NAME),
                   lambda result: result,
                   sleep_time=5)

        result = execute_ssh_command(client, 'ls /dev')
        client.close()
        logger.info('Files in /dev: %s', result)
        self.assertTrue('vdb\n' in result)

    #@check_quota_usages
    def test_boot_with_ephemeral(self):
        logger.info("-----------------------------------------------")
        logger.info("Starting boot instance with ephemeral test")
        logger.info("-----------------------------------------------")

        # Add keypair
        logger.info("Adding new pub key")
        keypair = self.nova.keypairs.create(self.KEY_NAME)
        f = open(self.KEY_FILE_NAME, 'w')
        f.write(keypair.private_key)
        f.close()

        # boot instance
        logger.info("Booting new instance: %s", self.INSTANCE_NAME)
        flavor = self.nova.flavors.find(name=self.flavor)
        image = self.nova.images.find(name=self.image)
        server_id = self.nova.servers.create(self.INSTANCE_NAME,
                                             image=image,
                                             key_name=self.KEY_NAME,
                                             flavor=flavor,
                                             availability_zone=self.availability_zone).id

        logger.info("Instance %s is building",  server_id)
        newserver = None
        try:
            newserver = poll_until(lambda: self.nova.servers.get(server_id),
                                   lambda inst: inst.status != 'BUILD',
                                   sleep_time=5)
        except PollTimeout as e:

            resized_server = e.previous_result
            error_message = 'Instance is stuck in BUILD.\n' \
                            'Instance ID = ' + server_id + '\n'
            if resized_server is not None:
                error_message = error_message + 'Host ID = ' + resized_server.hostId + '\n' \
                                                'Network = ' + str(resized_server.networks) + '\n'
            self.fail(error_message)
        finally:
            if newserver is not None:
                logger.info(vars(newserver))

        self.assertEquals('ACTIVE', newserver.status, 'The instance %(id)s is in %(status)s' % {'id': server_id, 'status': newserver.status})
        logger.info("Instance %s is active",  server_id)

        # sleep 10 seconds for instance to be ready (ssh server)
        time.sleep(10)

        secGroupExists = False
        groups = self.nova.security_groups.list()
        for group in groups:
            if group.name == self.SECGROUP_NAME:
                secGroupExists = True
                break
        if not secGroupExists:
            logger.info("Creating new security group + rules")
            secgroup = self.nova.security_groups.create(self.SECGROUP_NAME,
                                                        'test_boot_with_ephemeral')
            self.nova.security_group_rules.create(secgroup.id, 'tcp', 22, 22, '0.0.0.0/0')

        self.nova.servers.add_security_group(server_id, self.SECGROUP_NAME)

        # Ensure secgroup is not open
        logger.info("Network label for instance %s: %s", server_id, newserver.networks)
        network = newserver.networks[self.network_label][-1]

        logger.info('SSHing to %s', network)
        client = ssh.SSHClient()
        client.load_host_keys('/dev/null')
        client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        try:
            poll_until(lambda: check_for_exception(client.connect,
                                                   network,
                                                   username='ubuntu',
                                                   key_filename=self
                                                   .KEY_FILE_NAME),
                       lambda result: result,
                       sleep_time=5)
            logger.info('Check for /dev/vdb...')
            _, stdout, _ = client.exec_command('ls /dev')
            result = stdout.readlines()
            self.assertTrue('vdb\n' in result, '/dev/vdb not found')

            # Test outbound connectivity
            logger.info("Pinging google.com...")
            exit_status = 0
            for x in range(0, 5):
                _, stdout, stderr = client.exec_command('ping google.com -c 1')

                while not stdout.channel.exit_status_ready():
                    if stdout.channel.recv_ready():
                        rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                        if len(rl) > 0:
                            # Print data from stdout
                            logger.info(stdout.channel.recv(1024))
                    if stderr.channel.recv_stderr_ready():
                        rl, wl, xl = select.select([stderr.channel], [], [], 0.0)
                        if len(rl) > 0:
                            # Print data from stderr
                            logger.error(stderr.channel.recv_stderr(1024))
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    break
                else:
                    # sleep for 5 secs to allow network to be ready
                    time.sleep(5)
            self.assertEquals(0, exit_status, 'Ping to google.com failed!')
        except PollTimeout:
            error_message = 'Unable to SSH to ' + network + '\n' \
                            'Instance ID = ' + newserver.id + '\n' \
                            'Host ID = ' + newserver.hostId + '\n' \
                            'Status = ' + newserver.status + '\n' \
                            'Network = ' + str(newserver.networks) + '\n'
            self.fail(error_message)
        finally:
            client.close()


    #@check_quota_usages
    def test_security_group(self):
        logger.info("-----------------------------------------------")
        logger.info("Starting security group test")
        logger.info("-----------------------------------------------")

        open_port = 50000
        close_port = 50001

        # create script to start listener
        user_data = StringIO.StringIO()
        user_data.write('#!/bin/bash\n')
        user_data.write('while [ 1 ]; do nc -l {0}; done\n'.
                        format(open_port))
        content = user_data.getvalue()
        user_data.close()

        # Add keypair
        logger.info("Adding new pub key")
        keypair = self.nova.keypairs.create(self.KEY_NAME)
        f = open(self.KEY_FILE_NAME, 'w')
        f.write(keypair.private_key)
        f.close()

        # boot instance
        logger.info("Booting new instance: %s", self.INSTANCE_NAME)
        flavor = self.nova.flavors.find(name=self.flavor)
        image = self.nova.images.find(name=self.image)
        server_id = self.nova.servers.create(self.INSTANCE_NAME,
                                             image=image,
                                             userdata=content,
                                             key_name=self.KEY_NAME,
                                             flavor=flavor,
                                             availability_zone=self.availability_zone).id
        logger.info("Instance %s is building",  server_id)
        newserver = poll_until(lambda: self.nova.servers.get(server_id),
                               lambda inst: inst.status != 'BUILD',
                               sleep_time=5)
        self.assertEquals('ACTIVE', newserver.status)
        logger.info("Instance %s is active",  server_id)
        logger.info(vars(newserver))

        # create sec group + rule
        logger.info("Creating new security group + rules")
        secgroup = self.nova.security_groups.create(self.SECGROUP_NAME,
                                                    'Test security group')
        self.nova.security_group_rules.create(secgroup.id, 'tcp',
                                              open_port,
                                              open_port, '0.0.0.0/0')
        self.nova.servers.add_security_group(server_id, self.SECGROUP_NAME)
        logger.info("Network label for instance %s: %s", server_id, newserver.networks)
        network = newserver.networks[self.network_label][-1]
        logger.info('Telnetting to %s:%s', network, open_port)
        check_sec_group = poll_until(lambda: check_for_exception(telnetlib
                                                                 .Telnet,
                                                                 network,
                                                                 open_port,
                                                                 5 * MINUTE),
                                     lambda result: result,
                                     sleep_time=5)
        self.assertTrue(check_sec_group)

        self.assertRaises(Exception, telnetlib.Telnet, network, close_port,
                          5 * MINUTE)

    def cleanup(self):
        if self.skip_cleanup:
            return

        logger.info("Cleaning resources created by test")

        # Remove any instances with a matching name.
        previous = re.compile('^' + self.INSTANCE_NAME)
        for server in self.nova.servers.list():
            if previous.match(server.name):

                sec_group_names = [sg for sg in server.security_groups
                                   if sg['name'] == self.SECGROUP_NAME]
                if sec_group_names:
                    try:
                        self.nova.servers.remove_security_group(server.id, self.SECGROUP_NAME)
                    except Exception:
                        logger.exception("Cannot remove security group %s for instance %s",
                                         self.SECGROUP_NAME, server.id)
                logger.info("Deleting instance %s", server.id)
                self.nova.servers.delete(server.id)

        try:
            poll_until(lambda: [server for server in self.nova.servers.list()
                                if previous.match(server.name)],
                       lambda server_list: not server_list,
                       sleep_time=5)
        except PollTimeout:
            logger.info('Instance %s could not be deleted' % (server.name,))
            logger.info('Trying to delete again')
            self.nova.servers.delete(server.id)
            try:
                poll_until(lambda: [server for server in self.nova.servers.list()
                                    if previous.match(server.name)],
                           lambda server_list: not server_list,
                           sleep_time=5)
            except PollTimeout:
                self.fail('Instance %s could not be deleted' % (server.name,))
        finally:

            # Remove any image with a matching name.
            previous = re.compile('^' + self.IMAGE_NAME)
            for image in self.nova.images.list():
                if previous.match(image.name):
                    logger.info("Deleting image %s", image.name)
                    self.nova.images.delete(image.id)

            if self.volume_enable:
                # Remove any volume with a matching name.
                previous = re.compile('^' + self.VOLUME_NAME)
                for volume in self.cinder.volumes.list():
                    if previous.match(volume.display_name):
                        if volume.status == 'available':
                            logger.info("Deleting volume %s", volume.display_name)
                            self.cinder.volumes.delete(volume.id)

            # Remove key pair with a matching name.
            previous = re.compile('^' + self.KEY_NAME)
            for key_pair in self.nova.keypairs.list():
                if previous.match(key_pair.name):
                    logger.info("Deleting keypair %s", key_pair.name)
                    self.nova.keypairs.delete(key_pair.id)

            key_file = self.KEY_FILE_NAME
            if os.path.exists(key_file):
                os.remove(key_file)