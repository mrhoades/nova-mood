#!/usr/bin/env python
import logging
import re
import subprocess
import signal
import socket
import sys
import time
import traceback

from datetime import datetime
from datetime import timedelta
from functools import wraps
from time import sleep
from collections import Iterable
from novaclient.v1_1 import client
from structs.throttle import Throttle
from structs.server import Server
from structs.object_with_id import Object


nova_throttle = Throttle()
logging.basicConfig(format='%(asctime)s\t%(name)-16s %(levelname)-8s %(message)s')
logger = logging.getLogger('nova_test')
logger.setLevel(logging.DEBUG)


def nova_collector(tries=5, delay=5, back_off=2, throttle=nova_throttle.default_throttle,
                   bool_sync=nova_throttle.bool_sync_requests, logger=logger):
    def decorator(f):
        @wraps(f)
        def function_decorator(*args, **kwargs):
            local_tries, local_delay, result = tries, delay, None
            while local_tries > 0:
                start, finish, error_type, error_text = None, None, '', ''
                try:
                    logger.debug("{0}{1}".format(f.func_name, args_tostring(*args)))

                    if bool_sync is True:
                        nova_request_lock.acquire()

                    sleep(throttle)

                    start = datetime.now()
                    return f(*args, **kwargs)

                except Exception, e:
                    error_text = "EXCEPTION in throttle with function: {0} {1} {2}"\
                        .format(str(f.func_name), str(e), args_tostring(*args))

                    print error_text
                    trace_inner_exception()

                    if local_tries > 1:
                        print "Sleep {0} and then retry {1} more times...".format(local_delay, local_tries)
                        sleep(local_delay)
                        local_tries -= 1
                        local_delay *= back_off
                    else:
                        raise Exception("EXIT WITH HARD EXCEPTION at: " + error_text)
                finally:
                    finish = datetime.now()

                    if bool_sync is True:
                        nova_request_lock.release()

                    if nova_stats:
                        nova_stats.add_action_stat(f.func_name, start, finish,
                                                   get_error_type(error_text), str(error_text))

                    if test_timed_out:
                        msg = 'Test timed out while at Function: {0} after running ' \
                              'for {1} minutes'.format(str(f.func_name), test_time_limit)
                        raise Exception(msg)
        return function_decorator
    return decorator


def trace_inner_exception():

    if logging.DEBUG:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        print exc_type
        tb_list = traceback.extract_tb(sys.exc_info()[2])
        tb_list = traceback.format_list(tb_list)
        for elt in tb_list:
            print elt


def get_error_type(error_string):

    error_text = str(error_string).lower()

    if error_text == '':
        return ''
    elif 'http 429' in error_text or 'rate-limited' in error_text or 'rate limit' in error_text:
        return "(HTTP 429) Rate Limited"
    elif 'http 404' in error_text and 'not found' in error_text:
        return "(HTTP 404) Resource Not Found"
    elif 'http 400' in error_text and 'nw_info cache associated with instance' in error_text:
        return "(HTTP 404) No nw_info cache associated with instance"
    elif 'ssh timeout' in error_text:
        return "SSH Timeout"
    elif 'ping timeout' in error_text:
        return "Ping Timeout"
    elif 'delete server timeout' in error_text:
        return "Delete Server Timeout"
    elif 'floating ip attach failed' in error_text:
        return "Floating IP Attach Failed"
    elif 'bad request' in error_text or '400' in error_text:
        return "Malformed Request"
    else:
        return error_string


def rate_limit(max_per_second=5):
    min_interval = 1.0 / float(max_per_second)

    def decorate(func):
        time_last_called = [0.0]

        def rate_limit_function(*args, **kwargs):
            time_elapsed = time.clock() - time_last_called[0]
            time_to_wait = min_interval - time_elapsed
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            ret = func(*args, **kwargs)
            time_last_called[0] = time.clock()

            return ret
        return rate_limit_function
    return decorate


def args_tostring(*args):
    args_out = ''
    try:
        for count, thing in enumerate(args):
            args_out += str(thing)
        # print 'ARGS: ' + args_out
    except Exception as e:
        print e
    finally:
        return args_out


class Object:
    def __init__(self, id):
        self.id = id


class NovaServiceTest(object):
    """Class to manage creating and deleting nova instances"""
    @property
    def __name__(self):
        return 'NovaServiceTest'

    def __init__(self,
                 username=None,
                 password=None,
                 tenant_name=None,
                 project_id=None,
                 api_key=None,
                 auth_url=None,
                 region=None,
                 keypair=None,
                 security_group=None,
                 auth_ver='2.0',
                 count=1,
                 instance_name='',
                 test_name='',
                 timeout=20,
                 availability_zone='',
                 action_sleep_interval=1,
                 nova_assign_floating_ip=False,
                 flavor='',
                 image='',
                 lock=None,
                 throttle_in=None,
                 stats=None):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.project_id = project_id
        self.api_key = api_key
        self.auth_url = auth_url
        self.region = region
        self.keypair = keypair
        self.security_group = security_group
        self.auth_ver = auth_ver
        self.count = count
        self.test_name = test_name
        self.instance_name = instance_name
        self.flavor = flavor
        self.image = image
        self.availability_zone = availability_zone
        self.action_sleep_interval = action_sleep_interval
        self.nova_assign_floating_ip = nova_assign_floating_ip
        self.nova = None
        self.server = {}
        self.servers = []
        self.floating_ips = []
        self.test_exception_list = []

        global nova_request_lock
        nova_request_lock = lock
        global Throttle
        Throttle = throttle_in
        global test_timed_out
        test_timed_out = False
        global test_time_limit
        test_time_limit = timeout
        global nova_stats
        nova_stats = stats

        signal.signal(signal.SIGALRM, self.signal_handler)
        signal.alarm(timeout * 60)

        # self.changes_since = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        # self.path = os.path.dirname(__file__)
        # if not self.path:
        #     self.path = '.'

    def __getitem__(self, k):
        return k

    def signal_handler(self, signum, frame):
        global test_timed_out
        test_timed_out = True

    @nova_collector(throttle=nova_throttle.connect)
    def connect(self, force=False):
        """If we haven't already created a nova client, create one."""
        if self.nova and not force:
            return

        logger.info('Connect to HP Cloud User Account: ' + self.username)

        self.nova = client.Client(username=self.username,
                                  api_key=self.password,
                                  project_id=self.tenant_name,
                                  auth_url=self.auth_url,
                                  region_name=self.region,
                                  service_type="compute")

    def rate_limit_buster_warmup(self, iterations):
        """ Nova (and or some tool in between) tracks how many requests have been made in the last x seconds,
            with a limit of possibly 5 rps. This method fills that queue."""

        logger.info('Warm up rate-limit-buster.')
        total_requests_count = 0

        for i in range(iterations):
            total_requests_count += 1
            self.nova.servers.list()
            sleep(.1)
            total_requests_count += 1
            self.nova.floating_ips.list()
            sleep(.1)
        return total_requests_count

    def rate_limit_buster_find_rps(self):

        """ What is novaaazzzzz mood today?
            Find out how long to sleep after making requests, to avoid hitting rate limit errors."""

        logger.info('Try and determine how fast the tests can run without hitting rate-limits.')

        test_for_minutes = 10  # length of time analysis is run (6-12 minutes should do)
        base_sleep = .6  # how much time should job chill in between requests (.5 = almost 60 requests per minute)
        speed_increment_increase = .005
        speed_increment_slow_down = .02
        warm_up = True
        total_requests_count = 0
        count_since_last_exception = 0
        server_name = 'find-happy-request-rate'
        stop_time = datetime.now() + timedelta(minutes=test_for_minutes)

        while stop_time > datetime.now():
            try:
                if warm_up:
                    warm_up = False
                    total_requests_count += self.rate_limit_buster_warmup(30)

                total_requests_count += 1
                server = self.server_create_no_retry(server_name)
                sleep(base_sleep)

                # pump a few extra non-sleeping requests in here to ensure rate limit is maxing out
                total_requests_count += 1
                self.nova.servers.list()
                total_requests_count += 1
                self.nova.floating_ips.list()
                total_requests_count += 1
                self.nova.servers.list()
                total_requests_count += 1
                self.nova.servers.list()

                total_requests_count += 1
                self.server_delete_no_retry(server)
                sleep(base_sleep)

                count_since_last_exception += 1

                if count_since_last_exception >= 3 and base_sleep > 0.1:
                    # speed shit up
                    base_sleep -= speed_increment_increase
                    logger.info('SPEED_UP: ' + str(base_sleep))
                    count_since_last_exception = 0

            except Exception as e:
                logger.info(e.message)
                warm_up = False
                base_sleep += speed_increment_slow_down
                logger.info('SLOW_DOWN: ' + str(base_sleep))
                sleep(base_sleep)
                count_since_last_exception = 0
                exceptions_in_a_row = 0

                continue

        # TODO bugbugbug - rps isn't printed correctly - shows 0 - fix it
        requests_per_second = total_requests_count / (60 * test_for_minutes)
        logger.info('TOTAL REQUESTS MADE TO NOVA: ' + str(total_requests_count))
        logger.info('NOVA RPS WITHOUT ERROR: ' + str(requests_per_second))
        self.action_sleep_interval = base_sleep

    def add_test_instance(self, new_id):
        """Add the given server id to our server data structure."""
        self.server[new_id] = {}
        self.server[new_id]['time'] = {}
        self.server[new_id]['time']['create_start'] = datetime.now()
        logger.info("Creating server {0}".format(new_id))

    def fill_add_server_object(self, server):
        logger.debug('Fill new server data structure and add to server list')
        server_object = Server(id=server.id, name=server.name)
        self.servers.append(server_object)
        return server_object

    @nova_collector(throttle=nova_throttle.boot_instance, logger=logger)
    def boot(self, name):
        logger.info('Boot instance with name {0}'.format(name))
        self.instance_name = name
        if self.availability_zone == '':
            return self.nova.servers.create(name=name,
                                            image=self.image,
                                            flavor=self.flavor,
                                            key_name=self.keypair,
                                            security_groups={self.security_group})
        else:
            return self.nova.servers.create(name=name,
                                            image=self.image,
                                            flavor=self.flavor,
                                            key_name=self.keypair,
                                            availability_zone=self.availability_zone,
                                            security_groups={self.security_group})

    @nova_collector()
    def server_create_no_retry(self, name):
        newserver = self.nova.servers.create(name=name,
                                             image=self.image,
                                             flavor=self.flavor,
                                             key_name=self.keypair,
                                             availability_zone=self.availability_zone,
                                             security_groups={self.security_group})
        return newserver

    @nova_collector(tries=1)
    def server_delete_no_retry(self, server_id):
        self.nova.servers.delete(server_id)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests, throttle=nova_throttle.delete_instance)
    def server_delete(self, server):
        logger.info("Delete server with ID: {0} - NAME: {1}".format(server.id, server.name))
        self.nova.servers.delete(server.id)

    @nova_collector(bool_sync=nova_throttle.bool_sync_float_ip, throttle=nova_throttle.floating_ip_attach)
    def server_attach_floating_ip(self, nova_server_object, floating_ip):
        logger.info("Attach floating IP {0} to server {1}".format(floating_ip, nova_server_object.name))
        nova_server_object.add_floating_ip(floating_ip)
        self.verify_floating_ip_attached(nova_server_object, floating_ip.ip)

    @nova_collector(bool_sync=False, tries=1, throttle=nova_throttle.floating_ip_attach)
    def verify_floating_ip_attached(self, nova_server_object, ip):
        logger.info("Verify floating IP {0} is attached to server {1}".format(ip, nova_server_object.name))

        # bugbugbug - hard code sleep here for now.
        # there might be a delay between attach ip and db recognizing attach
        # should loop for 20 seconds or so maybe, raise error if attach didn't work
        sleep(5)
        new_server_object = self.nova_show_server(nova_server_object.id)
        if str(ip) not in str(new_server_object.addresses):
            raise Exception('SOFT ERROR: Floating IP Attach Failed: Floating ip {0} did not '
                            'attach to server {1}.'.format(ip, nova_server_object.name))

    @nova_collector(bool_sync=nova_throttle.bool_sync_float_ip, throttle=nova_throttle.floating_ip_attach)
    def server_detach_floating_ip(self, nova_server_object, floating_ip):
        logger.info("Detach floating IP {0} from server {1}".format(floating_ip, nova_server_object.name))
        nova_server_object.remove_floating_ip(floating_ip)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests, throttle=nova_throttle.get_server_list)
    def servers_get_list(self):
            return self.nova.servers.list()

    @nova_collector(bool_sync=False, tries=1, throttle=0)
    def floating_ip_attach_new(self, server, pool=None):
        address_object = self.floating_ip_create()
        nova_server_object = self.nova_show_server(server.id)
        self.server_attach_floating_ip(nova_server_object, address_object)
        server.update_floating_ip(address_object)
        self.floating_ips.append(server.ip_floating)

    @nova_collector(bool_sync=False, tries=1, throttle=0)
    def floating_ip_deallocate(self, server, ip):
        fip_object = self.floating_ip_get_object(ip)
        self.server_detach_floating_ip(server, fip_object)
        self.floating_ip_delete(fip_object)
        self.floating_ips.remove(ip)

    @nova_collector(bool_sync=False, tries=5, throttle=0)
    def floating_ip_attach_new_or_used(self, server):
        nova_server_object = self.nova_show_server(server.id)
        for float_ip in self.floating_ips_get_list():
            if float_ip.instance_id is None:
                logger.debug("Try attaching existing floating IP {0} to server {1}".format(float_ip, server.name))
                nova_server_object.add_floating_ip(float_ip)
                logger.debug("Attached floating IP {0} to server {1}".format(float_ip, server.name))
                server.update_floating_ip(float_ip)
                self.floating_ips.append(server.ip_floating)
                return
        float_ip = self.floating_ip_create()
        logger.info("Created new floating IP {0}".format(float_ip))
        logger.info("Try attaching floating IP {0} to server {1}".format(float_ip, server.name))
        nova_server_object.add_floating_ip(float_ip)
        logger.info("Attached floating IP {0} to server {1}".format(float_ip, server.name))
        server.update_floating_ip(float_ip)
        self.floating_ips.append(server.ip_floating)

    @nova_collector(bool_sync=nova_throttle.bool_sync_float_ip, throttle=nova_throttle.floating_ip_create)
    def floating_ip_create(self, pool=None):
        logger.info('Attempt to provision a new floating IP')
        # pool logic no worky in bravo
        # float = self.nova.floating_ips.create(pool=pool)
        float = self.nova.floating_ips.create()
        logger.info('Created new floating IP {0}'.format(float))
        return float

    @nova_collector(bool_sync=nova_throttle.bool_sync_float_ip, throttle=nova_throttle.floating_ip_delete)
    def floating_ip_delete(self, nova_floating_ip_object):
        logger.info('Delete Floating IP {0}'.format(str(nova_floating_ip_object)))
        self.nova.floating_ips.delete(nova_floating_ip_object)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests, throttle=nova_throttle.floating_ip_list)
    def floating_ips_get_list(self):
        return self.nova.floating_ips.list()

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests, throttle=nova_throttle.floating_ip_list)
    def floating_ip_get_id(self, floating_ip):
        for fip in self.nova.floating_ips.list():
            if fip.ip == floating_ip:
                return fip.id

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests, throttle=nova_throttle.floating_ip_list)
    def floating_ip_get_object(self, floating_ip):
        for fip in self.nova.floating_ips.list():
            if fip.ip == floating_ip:
                return fip

    @nova_collector(bool_sync=False, throttle=0)
    def set_flavor(self, flavor):
        """Lookup the specified flavor."""
        logger.info("Set instance flavor to {0}".format(flavor))
        self.flavor = self.nova.flavors.find(name=flavor)

    @nova_collector(bool_sync=False, throttle=0)
    def get_flavor_object(self, flavor):
        logger.info("Get flavor object for {0}".format(flavor))
        nova_flavor_object = self.nova.flavors.find(name=flavor)
        return Object(nova_flavor_object.id)

    @nova_collector(bool_sync=False, throttle=0)
    def set_image(self, image):
        """Lookup the specified image."""
        logger.info("Set instance image to {0}".format(image))
        self.image = self.nova.images.find(name=image)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests)
    def security_group_rule_create(self, parent_group_id, ip_protocol, from_port, to_port, cidr, group_id=None):
        group_rule = self.nova.security_group_rules.create(parent_group_id=parent_group_id,
                                                           ip_protocol=ip_protocol,
                                                           from_port=from_port,
                                                           to_port=to_port,
                                                           cidr=cidr,
                                                           group_id=group_id)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests)
    def security_group_create(self, name, description):
        return self.nova.security_groups.create(name, description)

    @nova_collector(bool_sync=nova_throttle.bool_sync_requests)
    def security_group_exists(self, name):
        groups = self.nova.security_groups.list()
        for group in groups:
            if group.name == name:
                return True
        return False

    @nova_collector(bool_sync=False)
    def get_image_object(self, image):
        logger.info("Get image object for {0}".format(image))
        nova_image_object = self.nova.images.find(name=image)
        return Object(nova_image_object.id)

    @nova_collector(tries=1, bool_sync=False)
    def wait_for_active_status(self, server, timeout_seconds=180):
        logger.info("Wait for server {0} to be ACTIVE".format(server.name))
        sleep(Throttle.status_check_delay)

        nova_server = None
        stop_time = datetime.now() + timedelta(minutes=timeout_seconds)

        while stop_time > datetime.now():

            nova_server = self.nova_show_server(server.id)
            if nova_server:
                # hpcloud 1.1 style server object output
                if 'OS-EXT-STS:task_state' in nova_server._info:

                    vm_state = str(nova_server._info['OS-EXT-STS:vm_state']).lower()
                    task_state = str(nova_server._info['OS-EXT-STS:task_state']).lower()
                    logger.info("Server {0} task_state is '{1}'".format(nova_server.name, task_state))

                    if task_state == "scheduling":
                        server.status = 'scheduling'
                        sleep(15)
                    elif vm_state == 'building' and task_state == 'none':
                        sleep(15)
                        pass
                    elif task_state == "networking":
                        server.status = 'networking'
                        sleep(10)
                    elif task_state == "block_device_mapping":
                        server.status = 'block_device_mapping'
                        sleep(5)
                    elif task_state == "spawning":
                        server.status = 'spawning'
                        sleep(2)
                    elif vm_state == 'active'and task_state == 'none':
                        server.status = 'active'
                        return nova_server
                    elif vm_state == "error":
                        server.status = 'error'
                        if isinstance(nova_server, Iterable) and 'fault' in nova_server:
                            server.fault = nova_server.fault
                        msg = 'Server {0} status is error: fault is {1}'.format(server.name, str(server.fault))
                        raise Exception(msg)
                    else:
                        logger.warning("wait_for_active_status - unknown status - vm_state is '{0}' and task_state "
                                       "is '{1}' for server {2}".format(vm_state, task_state, nova_server.name))
                        server.status = 'unknown'
                        sleep(8)

                # hpcloud 1.0 style server object output
                elif nova_server.status:
                    logger.info("Server {0} state is {1}".format(nova_server.name, nova_server.status))

                    if nova_server.status == "BUILD(scheduling)":
                        server.status = 'BUILD(scheduling)'
                        sleep(15)
                    elif nova_server.status == "BUILD(networking)":
                        server.status = 'BUILD(networking)'
                        sleep(10)
                    elif nova_server.status == "BUILD(block_device_mapping)":
                        server.status = 'BUILD(block_device_mapping)'
                        sleep(5)
                    elif nova_server.status == "BUILD(spawning)":
                        server.status = 'BUILD(spawning)'
                        sleep(2)
                    elif str(nova_server.status).startswith('BUILD'):
                        server.status = 'BUILD'
                        sleep(1)
                    elif nova_server.status == "ACTIVE(rebooting_hard)":
                        server.status = 'REBOOT_HARD'
                        sleep(15)
                    elif nova_server.status == "ACTIVE":
                        server.status = 'ACTIVE'
                        return nova_server
                    elif nova_server.status == "ERROR" or nova_server.status == "ERROR(networking)":
                        server.status = 'ERROR(networking)'
                        if isinstance(nova_server, Iterable) and 'fault' in nova_server:
                            server.fault = nova_server.fault
                        msg = 'Server {0} status is ERROR: fault is {1}'.format(server.name, str(server.fault))
                        raise Exception(msg)

                sleep(Throttle.poll_status)

        raise Exception("TIMEOUT Exception after waiting {0} seconds for VM ID '{1}' "
                        "to reach ACTIVE state.".format(timeout_seconds, server.id))

    @nova_collector(tries=1, bool_sync=False)
    def wait_for_deletion(self, server, timeout_seconds=180):
        logger.info("Wait for server with ID: {0} - NAME: {1} to be DELETED".format(server.id, server.name))

        # TODO: remove hard coded timeout here
        stop_time = datetime.now() + timedelta(seconds=timeout_seconds)
        nova_server = None

        while stop_time > datetime.now():
            error_msg = None
            try:
                logger.info("Check if server with ID: {0} - NAME: {1} EXISTS".format(server.id, server.name))
                nova_server = self.nova_show_server_no_logging(server.id)
                if nova_server is None:
                    # there appears to be a race condition with Quota around deletion
                    # let things simmer for a moment
                    sleep(10)
                    return True
            except Exception as e:
                error_msg = str(e)
                logger.info(error_msg)
                if 'timed out' in str(e.message):
                    raise Exception(e.message)
            finally:
                if error_msg is not None and ('could not be found' in error_msg or 'HTTP 404' in error_msg):
                    logger.info("Server with ID: {0} - NAME: {1} DELETED Successfully".format(server.id, server.name))
                    sleep(10)
                    return True

            sleep(Throttle.poll_status)

        raise Exception('Delete Server Timeout Exception: waited {0} seconds for '
                        'server ID: {1} - NAME: {2}  to be DELETED.'.format(timeout_seconds, server.id, server.name))

    @nova_collector(tries=5, delay=3, back_off=4, throttle=nova_throttle.get_server_info)
    def nova_show_server(self, server_id):
        return self.nova.servers.get(server_id)

    @nova_collector(tries=1, bool_sync=False, throttle=0)
    def nova_show_server_no_retry(self, server_id):
        return self.nova.servers.get(server_id)

    def nova_show_server_no_logging(self, server_id):
        return self.nova.servers.get(server_id)

    @nova_collector(bool_sync=False, tries=1, throttle=0)
    def ping_device(self, ip, timeout_seconds=180):
        stop_time = datetime.now() + timedelta(seconds=timeout_seconds)

        while stop_time > datetime.now():

            try:
                ping = subprocess.Popen(['ping', '-q', '-n', '-c 3', str(ip)],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                logger.debug('Attempt to ping IP {0}'.format(ip))
                out, err = ping.communicate()
                error_code = ping.returncode
                if error_code == 0:
                    logger.info('Successfull ping IP {0}'.format(ip))
                    return True
                elif error_code == 1:
                    logger.debug('Host not found IP {0}'.format(ip))
                elif error_code == 2:
                    logger.debug('Ping timed out IP {0}'.format(ip))

                sleep(nova_throttle.poll_ping)
            except Exception as e:
                logger.info('Caught Exception while trying to ping {0} {1}'.format(ip, e))

        msg = 'PING TIMEOUT for IP {0} after trying for {1} seconds'.format(ip, timeout_seconds)
        logger.info(msg)
        raise Exception(msg)

    @nova_collector(bool_sync=False, tries=5, throttle=0)
    def reboot_hard(self, server):
        logger.info('Reboot server HARD {0}-{1}'.format(server.id, server.name))
        # no worky in bravo
        # self.nova.servers.reboot(server.id, reboot_type='HARD')
        self.nova.servers.reboot(server.id)

    @nova_collector(bool_sync=False, tries=1, throttle=0)
    def reboot_server_wait_for_active(self, server, wait_seconds=180):
        logger.info('WARNING - kick_server_wait_for_active {0}-{1}'.format(server.id, server.name))
        self.reboot_hard(server)
        self.wait_for_active_status(server, wait_seconds)
        pass

    @nova_collector(bool_sync=False, tries=1, throttle=0)
    def ssh(self, server, timeout_seconds=180, username='ubuntu'):

        logger.info('Try SSH to {0} : {1}'.format(server.name, server.ip_floating))

        stop_time = datetime.now() + timedelta(seconds=timeout_seconds)
        stiff_kick_time = datetime.now() + timedelta(seconds=timeout_seconds-20)

        while stop_time > datetime.now():

            ssh_proc, out, err, return_code = None, None, None, None

            try:
                ssh_proc = subprocess.Popen(['ssh',
                                            '-o StrictHostKeyChecking=no',
                                            '-o UserKnownHostsFile=/dev/null',
                                            '{0}@{1}'.format(username, server.ip_floating),
                                            'hostname'],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
                logger.info('Attempt ssh to IP {0}'.format(server.ip_floating))
                out, err = ssh_proc.communicate()
                return_code = ssh_proc.returncode

                if stiff_kick_time is not None and stiff_kick_time < datetime.now():
                    stiff_kick_time = None
                    self.reboot_server_wait_for_active(server, wait_seconds=timeout_seconds)
                    stop_time = datetime.now() + timedelta(seconds=timeout_seconds)

            except Exception as e:
                logger.info('Caught Exception while trying ssh {0}@{1} - {2} - '
                            '{3}'.format(username, server.ip_floating, server.name, e))

            finally:
                logger.debug('SSH Return Code: ' + str(return_code))
                logger.debug('SSH Request Output: ' + str(out))

                if return_code == 0 and out.find(server.name) > -1:
                    logger.info('Successfull ssh to IP {0} {1}'.format(server.ip_floating, server.name))
                    return True
                elif return_code == 1:
                    logger.debug('Host not found IP {0} {1}'.format(server.ip_floating, server.name))
                elif return_code == 2:
                    logger.debug('SSH to IP timed out {0} {1}'.format(server.ip_floating, server.name))
                elif return_code == 255:
                    logger.debug(str(err))
                    if 'Permission denied (publickey)' in err:
                        msg = 'Permission denied (publickey). During SSH from {0} to {1} {2}. Make sure the ' \
                              'execution host {0} has the expected private identity using ssh-add -L, to connect ' \
                              'to the newly booted node ' \
                              '{2}'.format(socket.gethostname(), server.ip_floating, server.name)
                        raise Exception(msg)
                else:
                    logger.debug(str(err))

            sleep(nova_throttle.poll_ssh)

        msg = 'SSH Timeout Error: FAILED ssh to IP {0}-{1} after trying for {2} ' \
              'seconds.'.format(server.ip_floating, server.name, timeout_seconds)
        logger.info(msg)
        raise Exception(msg)

    def delete_ip_and_servers_EVERY_SINGLE_ONE(self, eula_agree=False):
        """ be very careful with this - it deletes every floating ip and server in the attached account zone """
        # TODO bugbugbug - figure out a way to tag floating ips for tests runs so you can hard cleanup safely.
        # or figure out a way to ensure important IPs never get deleted.
        # this might mean checking in a list reserved IPs. then modify this code to ignore those lists.
        # why don't floating IP pools work in prod and bravo?
        if not eula_agree:
            logger.info('delete_ip_and_servers_EVERY_SINGLE_ONE - deletes EVERYTHING - only if you agree! Be '
                        'very cafeful with this, so as not to remove a DNS mapped IP that is in use.')
        else:
            for server in self.servers_get_list():
                    self.server_delete(server)
            for floating_ip in self.floating_ips_get_list():
                    self.floating_ip_delete(floating_ip)

        logger.info('COMPLETED delete_ip_and_servers_EVERY_SINGLE_ONE')

    def delete_servers_with_pattern(self, server_name_pattern, hosts_to_ignore=None):
        """ deletes all test servers match the supplied pattern, and the attached floating ip """
        regx_server = re.compile(server_name_pattern)

        for server in self.servers_get_list():
            if regx_server.match(server.name):
                if hosts_to_ignore is None or server.name not in hosts_to_ignore:
                    self.server_delete(server)

    def delete_floating_ips(self, ignore_ip_list=None):
        """ deletes all the floating ips in the account, except ips in supplied list """
        for floating_ip in self.floating_ips_get_list():
            if floating_ip.ip not in ignore_ip_list:
                self.floating_ip_delete(floating_ip)
