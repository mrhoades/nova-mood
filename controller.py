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
from troveclient import utils

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
    env = NovaTestInfo()            # construct test environment object
    env = parse_config_yaml(env)    # fill with yaml config
    env = parse_args(env)           # fill with args data
    pass

    cleanup_nova_test_env(env)
    cleanup_orphaned_float_ip_in_test_env(env, ignore_ip_list={'15.126.197.219'})
    create_perf_metric_security_group(env)
    nova_boot_scaling(env)

    # bugbugbug - test that are to be run should be defined in yaml or passed in somehow
    # bugbugbug - half baked trove scaling
    #test_trove_create_concurrently(env, 1)


@timeout(timeouts.parent_test)
def nova_boot_scaling(env):

    logger.info('BEGIN PARENT TEST: {0}'.format(env.test_name))
    pass_stats = NovaTestStats(test_name=env.test_name,
                               environ_name=env.env_name,
                               zone=env.availability_zone,
                               region=env.region,
                               execution_host=env.execution_hostname,
                               cloud_account_username=env.username)

    env.test_pass_id = nova_mood_db.create_new_test_pass(pass_stats)
    pass_stats.test_pass_id = env.test_pass_id

    try:
        cleanup_nova_test_env(env)
        env = get_flavor_and_image_objects(env)  # set image and flavor objects with env specific id's

        for i in range(boot_scaling.iterations):

            print 'sleep another {0} seconds - cool off before next iteration {1} of tests'.format(10 * i * i, i)
            sleep(10 * i * i)  # the heavier the load, the heavier the cool off
            test_nova_boot_concurrently(env, boot_scaling.instance_count_seed, boot_scaling.pool_workers)
            cleanup_nova_test_env(env)
            boot_scaling.instance_count_seed *= boot_scaling.multiplier
            boot_scaling.instance_count_seed += boot_scaling.bump_up

    except Exception as e:
        msg = 'ERROR IN TEST: {0} {1}'.format(env.test_name, e.message)
        logger.info(msg)
        print msg

    finally:
        pass_stats.ended()
        logger.info('END PARENT TEST: {0}'.format(env.test_name))
        logger.info('LOG RESULTS TO DB:  {0}'.format(env.test_name))
        nova_mood_db.update_test_pass(pass_stats)


@timeout(timeouts.test)
def test_nova_boot_concurrently(env, instance_count, pool_workers=None):

    logger.info('BEGIN: test_nova_boot_concurrently {0} instances'.format(instance_count))

    test_list = []
    test_results = []

    if pool_workers is None or pool_workers == -1:
        pool_workers = instance_count
    pool = multiprocessing.Pool(processes=pool_workers)

    # run asynchronous tests
    for i in range(instance_count):

        instance_name = generate_rand_instance_name(env.test_name + str(i))

        test_stats = NovaTestStats(test_name='test_nova_boot',
                                   environ_name=env.env_name,
                                   zone=env.availability_zone,
                                   region=env.region,
                                   execution_host=env.execution_hostname,
                                   cloud_account_username=env.username,
                                   test_pass_id=env.test_pass_id,
                                   concurrency_count=instance_count)
        env.test_case_stats[instance_name] = test_stats

        # TODO bugbugbug - make this generic so you can execute any test - move tests out of controller
        test_result = pool.apply_async(eval('test_nova_boot'), args=(instance_name, env, global_lock, throttle))
        test_list.append(test_result)
    pool.close()
    pool.join()

    while len(test_list) > 0:
        try:
            test_results.append(test_list[0].get(timeout=10))
            test_list.pop(0)
        except None:
            print 'err.. no.. yo..'

    logger.info('COMPLETE: test_nova_boot_concurrently {0} instances'.format(instance_count))


def test_nova_boot(instance_name, env, global_lock, throttle):
    logger.info('BEGIN TEST: test_nova_boot {0}'.format(instance_name))
    # auto-throttle this test by determining the current load
    # TODO: still need to develop algorithm for determining that magic number
    # rps = stats_queries.get_rps_for_environment(env.env_name, 1)
    # print 'RPS: ' + str(rps)

    nova, server, bool_error = None, None, False

    try:

        nova = NovaServiceTest(throttle_in=throttle,
                               lock=global_lock,
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
                               availability_zone=env.availability_zone,
                               action_sleep_interval=env.action_sleep_interval,
                               nova_assign_floating_ip=env.nova_assign_floating_ip,
                               flavor=env.flavor_object,
                               image=env.image_object,
                               stats=env.test_case_stats[instance_name])

        nova.connect()
        nova_server_object = nova.boot(instance_name)
        server = nova.fill_add_server_object(nova_server_object)

        nova_server_object = nova.wait_for_active_status(server, timeouts.wait_for_active)
        env.test_case_stats[instance_name].now_active()
        server.update_ips(nova_server_object.addresses)

        if env.nova_assign_floating_ip:
            nova.floating_ip_attach_new(server)

        if not env.skip_ping_device:
            nova.ping_device(server.ip_floating, timeouts.ping_instance)

        env.test_case_stats[instance_name].now_pingable()

        nova.ssh(server, timeouts.ssh_instance)
        env.test_case_stats[instance_name].now_sshable()

        if env.nova_assign_floating_ip:
            nova.floating_ip_deallocate(nova_server_object, server.ip_floating)

        nova.server_delete(server)
        nova.wait_for_deletion(server.id)

    except Exception as e:
        bool_error = True
        msg = 'ERROR IN TEST: {0} {1} {2}'.format('test_nova_boot', instance_name, e.message)
        logger.info(msg)
        print msg

        # TODO bugbugbug - make sure this error is in the stats logging (timeout - likely)

    finally:

        env.test_case_stats[instance_name].ended()

        logger.info('END TEST: test_nova_boot {0}'.format(instance_name))
        logger.info('LOG RESULTS TO DB: test_nova_boot {0}'.format(instance_name))

        test_stats = env.test_case_stats[instance_name]
        nova_mood_db.insert_test_results(test_stats)

        if bool_error:
            cleanup_server_safely(nova, server)
            if env.nova_assign_floating_ip:
                cleanup_floating_ip_safely(nova, server)


@timeout(timeouts.test)
def test_trove_create_concurrently(env, instance_count, pool_workers=None):

    # bugbugbug - hack in fake shit... so this will run
    env.test_pass_id = 50000

    logger.info('BEGIN: test_trove_create_concurrently {0} instances'.format(instance_count))

    test_list = []
    test_results = []

    if pool_workers is None or pool_workers == -1:
        pool_workers = instance_count
    pool = multiprocessing.Pool(processes=pool_workers)

    # run asynchronous tests
    for i in range(instance_count):

        instance_name = generate_rand_instance_name(env.test_name + str(i))

        test_stats = NovaTestStats(test_name='test_trove_create',
                                   environ_name=env.env_name,
                                   zone=env.availability_zone,
                                   region=env.region,
                                   execution_host=env.execution_hostname,
                                   cloud_account_username=env.username,
                                   test_pass_id=env.test_pass_id,
                                   concurrency_count=instance_count)
        env.test_case_stats[instance_name] = test_stats

        # TODO bugbugbug - make this generic so you can execute any test - move tests out of controller
        test_result = pool.apply_async(eval('test_trove_create'), args=(instance_name, env, global_lock, throttle))
        test_list.append(test_result)
    pool.close()
    pool.join()

    while len(test_list) > 0:
        try:
            test_results.append(test_list[0].get(timeout=10))
            test_list.pop(0)
        except None:
            print 'err.. no.. yo..'

    logger.info('COMPLETE: test_nova_boot_concurrently {0} instances'.format(instance_count))


def test_trove_create(instance_name, env, global_lock, throttle):
    logger.info('BEGIN TEST: test_trove_create {0}'.format(instance_name))

    nova, server, bool_error = None, None, False

    try:

        nova = NovaServiceTest(throttle_in=throttle,
                               lock=global_lock,
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
                               availability_zone=env.availability_zone,
                               action_sleep_interval=env.action_sleep_interval,
                               nova_assign_floating_ip=env.nova_assign_floating_ip,
                               flavor=env.flavor_object,
                               image=env.image_object,
                               stats=env.test_case_stats[instance_name])

        nova.connect_trove()

        # create a new trove db instance
        # wait for active status
        # get the fuckin root password
        # create a database on the instance

        # print all the database instances
        # utils.print_list(nova.trove.instances.list(), ['id', 'name', 'status', 'flavor_id', 'size'])


        # create a new trove db instance
        db_instance = nova.trove.instances.create(name=instance_name, flavor_id=1001)
        print db_instance
        print db_instance.id
        print db_instance.name
        print db_instance.status  # bullshit - its not fuckin active

        # wait for active status
        build_status = None
        while build_status != "ACTIVE":
            #bugbugbug - need timeout here
            sleep(10)
            db_instance = nova.trove.instances.get(db_instance)
            build_status = db_instance.status
            print 'DB BUILD STATUS now: ' + build_status

        print db_instance
        print db_instance.id
        print db_instance.name
        print db_instance.status
        print db_instance.ip[0]
        print db_instance.ip[1]

        # get the fuckin password
        password = nova.trove.root.create(db_instance.id)
        print password[1]
        nova.trove.users.update_attributes(db_instance.id, 'root', newuserattr={"password": "rnetpa55"})

        # create a database named "test" on the instance
        new_empty_db = nova.trove.databases.create(db_instance.id, [{"name": "test"}])
        print new_empty_db

        # initialize a schema
        import MySQLdb

        db_name = 'test'
        db_root_user = 'root'
        db_password = 'rnetpa55'
        db_hostname_or_ip = db_instance.ip[1]


        # run sysbench utlity

        # print results

        # delete the database
        nova.trove.instances.delete(db_instance)

        # wait for deletion
        pass

    except Exception as e:
        bool_error = True
        msg = 'ERROR IN TEST: {0} {1} {2}'.format('test_trove_create', instance_name, e.message)
        logger.info(msg)
        print msg

        # TODO bugbugbug - make sure this error is in the stats logging (timeout - likely)

    finally:

        # env.test_case_stats[instance_name].ended()
        logger.info('COMPLETED: test_trove_create {0}'.format(instance_name))
        #
        # test_stats = env.test_case_stats[instance_name]
        # nova_mood_db.insert_test_results(test_stats)
        #
        # if bool_error:
        #     cleanup_server_safely(nova, server)
        #     if env.nova_assign_floating_ip:
        #         cleanup_floating_ip_safely(nova, server)


def test_global_lock_speed(name, global_lock):

    logger.info('BEGIN TEST: test_global_lock_speed {0}'.format(name))
    try:
        logger.info('request lock: ' + name)
        global_lock.acquire()

        sleep(.1)

        logger.info('got lock: ' + name)
    except Exception as e:
        msg = 'ERROR IN TEST: {0} {1} {2}'.format('test_nova_boot', name, e.message)
        logger.info(msg)
    finally:
        logger.info('released lock: ' + name)
        global_lock.release()


@timeout(timeouts.cleanup_env_thread)
def cleanup_nova_test_env(env):
    logger.info('Cleanup test environment: {0}'.format(env.test_name))

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

        # nova.delete_servers_and_attached_floating_ips(env.test_name)
        nova.delete_servers_with_pattern(env.test_name)

        # TODO: load all these ignore ips from a config

        # TODO: bugbugbug - need to find a better way of cleaning up orphaned floating ips
        # nova.delete_floating_ips(ignore_ip_list={'15.185.188.49', '15.185.188.49', '15.185.103.238',
        #                                          '15.185.111.169', '15.185.113.81'})

        #  bugbugbug - wait for deletion old school style.
        # need a more definitive way to know that we're done with cleanup.
        print 'Sleep for 10 seconds and wait for deletions to clear out.'
        sleep(10)  # wait for test deletions to clear out
        print 'Cleanup complete!'
    except Exception as e:
        logger.info('ERROR IN TEST: cleanup_nova_test_env for parent job '.format(e))


def cleanup_server_safely(nova, server):
    try:
        if nova is not None:
            if server is not None:
                logger.info('Cleanup server {0} safely.'.format(server.name))
                nova.connect()
                nova.server_delete_no_retry(server.id)
    except Exception as e:
        if 'HTTP 404' in str(e):
            logger.info('Server not found - likely already cleaned up.'.format(e))
        else:
            logger.info('ERROR: failure with server cleanup'.format(e))


def cleanup_floating_ip_safely(nova, server):
    try:
        if nova is not None:
            if server is not None:
                if server.ip_floating is not None:
                    logger.info('Cleanup floating ip {0} safely.'.format(server.ip_floating))
                    nova.connect()
                    nova.floating_ip_delete(server.ip_floating)
    except Exception as e:
        if 'HTTP 404' in str(e):
            logger.info('Floating ip not found - likely already cleaned up.'.format(e))
        else:
            logger.info('ERROR: failure with floating ip cleanup'.format(e))


@timeout(timeouts.cleanup_env_thread)
def cleanup_all_float_ip_in_test_env(env, ignore_ip_list=None):
    logger.info('Cleanup test environment: {0}'.format(env.test_name))

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

        # nova.delete_floating_ips(ignore_ip_list={'15.185.188.49', '15.185.188.49', '15.185.103.238',
        #                                          '15.185.111.169', '15.185.113.81'})

        nova.delete_floating_ips(ignore_ip_list)

        #  bugbugbug - wait for deletion old school style.
        # need a more definitive way to know that we're done with cleanup.
        print 'Sleep for 10 seconds and wait for deletions to clear out.'
        sleep(10)  # wait for test deletions to clear out
        print 'Cleanup complete!'
    except Exception as e:
        logger.info('ERROR IN TEST: cleanup_nova_test_env for parent job '.format(e))


@timeout(300)
def cleanup_orphaned_float_ip_in_test_env(env, ignore_ip_list=None):

    if env.cleanup_orphaned_floating_ips:
        logger.info('Cleanup orphaned floating-ips in environment: {0}'.format(env.test_name))

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

            nova.delete_orphaned_floating_ips(ignore_ip_list)

            print 'Sleep for 10 seconds and wait for deletions to clear out.'
            sleep(10)  # wait for test deletions to clear out
            print 'Cleanup complete!'
        except Exception as e:
            logger.info('ERROR IN TEST: Cleanup orphaned floating-ips '.format(e))


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


def generate_rand_instance_name(test_name):
        instance_name = "{0}-{1}-{2}{3}{4}".format(test_name,
                                                   randint(100, 999),
                                                   random.choice(string.ascii_lowercase),
                                                   random.choice(string.ascii_lowercase),
                                                   random.choice(string.ascii_lowercase))
        return instance_name


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

    env.execution_hostname = socket.gethostbyaddr(socket.gethostname())[0]

    return env

if __name__ == '__main__':
    main()
