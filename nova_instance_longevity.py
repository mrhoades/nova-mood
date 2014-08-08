#!/usr/bin/env python
import logging
import os
import multiprocessing
import socket
import random
import string
import yaml
import nova_mood_db
from time import sleep
from random import randint
from decorators.timeout import timeout
from structs.nova_env_info import NovaTestInfo
from structs.nova_auth import NovaAuth
from structs.nova_test_stats import NovaTestStats
from structs.nova_mood_timouts import NovaMoodTimeouts
from structs.boot_scaling import BootScaling
from structs.throttle import Throttle
from nova_service_test import NovaServiceTest


logging.basicConfig(format='%(asctime)s\t%(name)-16s %(levelname)-8s %(message)s')
logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)

manager = multiprocessing.Manager()
global_lock = manager.Lock()
throttle = Throttle()
timeouts = NovaMoodTimeouts()
boot_scaling = BootScaling()
nova_auth = NovaAuth()


@timeout(timeouts.job)
def main():
    env = NovaTestInfo()                 # construct test environment object
    env = parse_config_yaml(env)    # fill with yaml config
    env = parse_args(env)               # fill with args data
    env.hard_rebuild = False            # use this switch to reconstruct the instances

    env = get_flavor_and_image_objects(env)  # set image and flavor objects with env specific id's
    create_perf_metric_security_group(env)

    # test_nova_instance_longevity(env, 'nova-instance-longevity-az1', 'az1', '15.125.72.139')
    # test_nova_instance_longevity(env, 'nova-instance-longevity-az2', 'az2', '15.125.115.198')
    # test_nova_instance_longevity(env, 'nova-instance-longevity-az3', 'az3', '15.125.127.170')

    test_nova_instance_longevity(env, 'nova-instance-longevity-ae1az1', 'dbaas-ae1az1-v1')
    test_nova_instance_longevity(env, 'nova-instance-longevity-ae1az2', 'dbaas-ae1az2-v1')
    test_nova_instance_longevity(env, 'nova-instance-longevity-ae1az3', 'dbaas-ae1az3-v1')

    # test_nova_instance_longevity(env, 'nova-instance-longevity-az2', 'az2')
    # test_nova_instance_longevity(env, 'nova-instance-longevity-az3', 'az3')


def test_nova_instance_longevity(env, instance_name, zone, assign_floating_ip=None, force_rebuild=False):

    """
    This test scenario boots instances if they don't exist, checks the happiness of
    the instances by ssh'ing into them and pinging google, and leaves them in
    place to test long term happiness. If there were an issue with connectivity
    to the instance, the test will fail. An option to perform a forceful rebuild is
    provided, in the event the instances can't be recovered.
    """

    logger.info('BEGIN TEST: test_nova_instance_longevity {0}'.format(instance_name))

    nova, nova_server_object, server, bool_error = None, None, None, False

    try:

        nova = NovaServiceTest(throttle_in=throttle,
                               username=env.username,
                               password=env.password,
                               tenant_name=env.tenant_name,
                               project_id=env.project_id,
                               auth_url=env.auth_url,
                               region=env.region,
                               keypair=env.key_name,
                               security_group=env.security_group,
                               auth_ver=env.auth_ver,
                               count=env.instance_count,
                               instance_name=env.instance_name,
                               test_name=env.test_name,
                               timeout=env.timeout_minutes,
                               availability_zone=zone,
                               action_sleep_interval=env.action_sleep_interval,
                               nova_assign_floating_ip=env.nova_assign_floating_ip,
                               flavor=env.flavor_object,
                               image=env.image_object)

        nova.connect()

        # force rebuild to clean env
        if force_rebuild is True:
            nova.delete_servers_with_pattern(instance_name)
            nova.wait_for_deletion(instance_name)

        # if the instance already exists, just build it's object, get it's ip address
        if nova.server_with_name_exists(instance_name):
            nova_server_object = nova.server_with_name_get(instance_name)
            server = nova.fill_add_server_object(nova_server_object)
        else:
            nova_server_object = nova.boot(instance_name)
            server = nova.fill_add_server_object(nova_server_object)
            nova.wait_for_active_status(server, timeouts.wait_for_active)

            if assign_floating_ip is not None:
                floating_ip_object = nova.floating_ip_get_object(assign_floating_ip)
                nova.server_attach_floating_ip(nova_server_object, floating_ip_object)
            nova_server_object = nova.server_with_name_get(instance_name)
            server = nova.fill_add_server_object(nova_server_object)

        #check the happiness of the instance
        # nova.ping_device(server.ip_floating, timeouts.ping_instance)
        nova.ssh(server, timeouts.ssh_instance)
        nova.ssh_remote_exec(server, 'ping -c3 www.google.com',
                             '3 packets transmitted, 3 received', timeouts.ssh_instance)

    except Exception as e:
        msg = 'ERROR IN TEST: {0} {1} {2}'.format('test_nova_boot', instance_name, e.message)
        logger.info(msg)
    finally:
        logger.info('END TEST: test_nova_boot {0}'.format(instance_name))


@timeout(timeouts.cleanup_env_thread)
def get_flavor_and_image_objects(env):
    logger.info('Get Image and Flavor Objects for REGION: {0} and AZ: '.format(env.region, env.availability_zone))

    try:
        nova = NovaServiceTest(lock=global_lock,
                               username=env.username,
                               password=env.password,
                               tenant_name=env.tenant_name,
                               project_id=env.project_id,
                               auth_url=env.auth_url,
                               region=env.region,
                               keypair=env.key_name,
                               auth_ver=env.auth_ver,
                               count=env.instance_count,
                               instance_name=env.instance_name,
                               test_name=env.test_name,
                               timeout=env.timeout_minutes,
                               availability_zone=env.availability_zone,
                               action_sleep_interval=env.action_sleep_interval)

        nova.connect()
        env.flavor_object = nova.get_flavor_object(env.flavor_name)
        env.image_object = nova.get_image_object(env.image_name)

    except Exception as e:
        logger.info('ERROR IN get_flavor_and_image_objects: '.format(str(e)))
    finally:
        return env


@timeout(timeouts.cleanup_env_thread)
def create_perf_metric_security_group(env):
    logger.info('Create perf metric security group if not exist: {0}'.format(env.security_group))

    try:
        nova = NovaServiceTest(lock=global_lock,
                               username=env.username,
                               password=env.password,
                               tenant_name=env.tenant_name,
                               project_id=env.project_id,
                               auth_url=env.auth_url,
                               region=env.region,
                               keypair=env.key_name,
                               auth_ver=env.auth_ver,
                               count=env.instance_count,
                               instance_name=env.instance_name,
                               test_name=env.test_name,
                               timeout=env.timeout_minutes,
                               availability_zone=env.availability_zone)

        nova.connect()

        if not nova.security_group_exists('perf-metrics'):
            group = nova.security_group_create('perf-metrics', 'ssh and ping ports')
            nova.security_group_rule_create(group.id, 'tcp', 22, 22, '0.0.0.0/0')
            nova.security_group_rule_create(group.id, 'icmp', -1, -1, '0.0.0.0/0')

    except Exception as e:
        logger.info('ERROR IN get_flavor_and_image_objects: '.format(str(e)))
    finally:
        return env


def parse_config_yaml(env):

    logger.info('BUGBUGBUG - need to finish yaml config parsing for all settings')

    dir_name, filename = os.path.split(os.path.abspath(__file__))
    with open(dir_name + '/config.yaml', 'r') as f:
        config = yaml.load(f)

        for member_name in sorted(vars(nova_auth)):
            eval_string = "nova_auth.{0} = '{1}'".format(member_name, str(config['nova_auth'][member_name]))
            logger.debug(eval_string)
            exec eval_string

        for member_name in sorted(vars(boot_scaling)):
            eval_string = "boot_scaling.{0} = {1}".format(member_name, str(config['boot_scaling'][member_name]))
            logger.debug(eval_string)
            exec eval_string

        for member_name in sorted(vars(timeouts)):
            eval_string = "timeouts.{0} = {1}".format(member_name, str(config['timeouts'][member_name]))
            logger.debug(eval_string)
            exec eval_string

        for member_name in sorted(vars(throttle)):
            eval_string = "throttle.{0} = {1}".format(member_name, str(config['throttle'][member_name]))
            logger.debug(eval_string)
            exec eval_string

    return env


def parse_args(env):

    from optparse import OptionParser

    op = OptionParser()
    op.add_option('-l', '--log-level', dest='log_level', type=str, default='info',
                  help='Logging output level.')
    op.add_option('-t', '--timeout', dest='timeout', type=int, default=20,
                  help='Timeout (in minutes) for creating or deleting instances')
    op.add_option('-r', '--hard-rebuild',
                  dest='hard_rebuild',
                  type=str,
                  default='False',
                  help='Setting hard rebuild to true will force deletion and recreation of instances')

    options, args = op.parse_args()

    if options.log_level.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        logger.setLevel(getattr(logging, options.log_level.upper()))

    env.username = os.environ['OS_USERNAME']
    env.password = os.environ['OS_PASSWORD']
    env.api_key = os.environ['OS_API_KEY']
    env.tenant_name = os.environ['OS_TENANT_NAME']
    env.auth_url = os.environ['OS_AUTH_URL']
    env.region = os.environ['OS_REGION_NAME']
    env.key_name = os.environ['OS_KEYPAIR']
    env.availability_zone = os.environ['OS_AVAILABILITY_ZONE']

    if 'OS_FLAVOR_NAME' in os.environ:
        env.flavor_name = os.environ['OS_FLAVOR_NAME']
    if 'OS_IMAGE_NAME' in os.environ:
        env.image_name = os.environ['OS_IMAGE_NAME']
    if 'SKIP_PING' in os.environ:
        env.skip_ping_device = os.environ['SKIP_PING'].lower() in ("yes", "true", "t", "1")
    if 'NOVA_INSTANCE_COUNT' in os.environ:
        env.instance_count = int(os.environ['NOVA_INSTANCE_COUNT'])
    if 'NOVA_NAME' in os.environ:
        env.nova_name = os.environ['NOVA_NAME']
        env.test_name = os.environ['NOVA_NAME']
    if 'NOVA_ENVIRON_NAME' in os.environ:
        env.env_name = os.environ['NOVA_ENVIRON_NAME']
    if 'NOVA_ACTION_SLEEP_INTERVAL' in os.environ:
        env.action_sleep_interval = int(os.environ['NOVA_ACTION_SLEEP_INTERVAL'])
    if 'NOVA_ASSIGN_FLOATING_IP' in os.environ:
        env.nova_assign_floating_ip = os.environ['NOVA_ASSIGN_FLOATING_IP'].lower() in ("yes", "true", "t", "1")
    if 'CLEANUP_ORPHANED_FLOATING_IPS' in os.environ:
        env.cleanup_orphaned_floating_ips = os.environ['CLEANUP_ORPHANED_FLOATING_IPS'].lower() \
            in ("yes", "true", "t", "1")
    if 'RUN_RATE_LIMIT_BUSTER' in os.environ:
        env.run_rate_limit_buster = os.environ['RUN_RATE_LIMIT_BUSTER'].lower() in ("yes", "true", "t", "1")
    if 'NOVA_SECURITY_GROUP' in os.environ:
        env.security_group = os.environ['NOVA_SECURITY_GROUP']
    if 'AVAILABILITY_ZONE_LABEL' in os.environ:
        env.availability_zone_label = os.environ['AVAILABILITY_ZONE_LABEL']
    if 'HARD_REBUILD' in os.environ:
        env.hard_rebuild = os.environ['HARD_REBUILD'].lower() in ("yes", "true", "t", "1")
    env.execution_hostname = socket.gethostbyaddr(socket.gethostname())[0]

    return env

if __name__ == '__main__':
    main()