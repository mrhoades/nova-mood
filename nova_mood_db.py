from datetime import datetime
from random import randint
from datetime import timedelta
from prettytable import from_db_cursor

import MySQLdb

db_name = 'nova_mood'
db_root_user = 'root'
db_password = 'please_set_password'
db_hostname_or_ip = 'please_set_ip'

def main():
    create_nova_mood_db(bool_drop_db=False)

    # # test inserting data
    # test_pass_id = test_add_test_pass()
    # tid = test_add_result_data(test_pass_id)
    # test_add_result_data_granular(tid)


def create_nova_mood_db(bool_drop_db=True):
    try:
        conn = get_mysql_connection()

        with conn:
            cur = conn.cursor()

            if bool_drop_db:
                print 'Detected drop the database switch. Drop DB: {0}'.format(db_name)
                cur.execute("DROP DATABASE {0};".format(db_name))

            print 'Create the database: {0}'.format(db_name)

            cur.execute('CREATE DATABASE IF NOT EXISTS {0};'.format(db_name))

            cur.execute("USE {0};".format(db_name))

            test_passes = '''CREATE TABLE IF NOT EXISTS `test_passes` (
                                          `test_pass_id` INT PRIMARY KEY AUTO_INCREMENT,
                                          `test_pass_name` varchar(50) NOT NULL,
                                          `environ_name` varchar(50) NOT NULL,
                                          `zone` varchar(25) NOT NULL,
                                          `region` varchar(40) NOT NULL,
                                          `execution_hostname` varchar(50) NOT NULL,
                                          `cloud_account_username` varchar(50) NOT NULL,
                                          `time_started` datetime NOT NULL,
                                          `time_end` datetime,
                                          `time_total` float
                                        ) ENGINE=InnoDB DEFAULT CHARSET=latin1'''
            cur.execute(test_passes)

            test_results = '''CREATE TABLE IF NOT EXISTS `test_results` (
                                          `test_id` INT PRIMARY KEY AUTO_INCREMENT,
                                          `test_pass_id` INT(20),
                                          `test_name` varchar(50) NOT NULL,
                                          `concurrency_count` INT(5),
                                          `time_started` datetime NOT NULL,
                                          `time_end` datetime NOT NULL,
                                          `time_total` float NOT NULL,
                                          `time_to_active` float NOT NULL,
                                          `time_to_ping` float NOT NULL,
                                          `time_to_ssh` float NOT NULL,
                                          `is_active` tinyint(1) NOT NULL,
                                          `is_pingable` tinyint(1) NOT NULL,
                                          `is_sshable` tinyint(1) NOT NULL,
                                          `is_successful` tinyint(1) NOT NULL,
                                          `rps` float NULL,
                                          `hard_errors_exist` bit(1) NOT NULL DEFAULT b'0',
                                          `hard_error_count` INT(3),
                                          `soft_error_count` INT(3),
                                          FOREIGN KEY (test_pass_id) REFERENCES test_passes(test_pass_id) ON DELETE CASCADE
                                        ) ENGINE=InnoDB DEFAULT CHARSET=latin1'''
            cur.execute(test_results)

            test_results_granular = '''CREATE TABLE IF NOT EXISTS `test_results_granular` (
                                        test_id INT(20),
                                        `function_name` varchar(50) NOT NULL,
                                        `time_started` datetime NOT NULL,
                                        `time_end` datetime NOT NULL,
                                        `time_total` float NOT NULL,
                                        `error_type` varchar(500),
                                        `error_text` varchar(1000),
                                        FOREIGN KEY (test_id) REFERENCES test_results(test_id) ON DELETE CASCADE
                                        ) ENGINE=InnoDB DEFAULT CHARSET=latin1'''

            cur.execute(test_results_granular)

    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def get_mysql_connection(user=db_root_user,
                         password=db_password,
                         hostname_or_ip=db_hostname_or_ip):
    return MySQLdb.connect(hostname_or_ip, user, password)


def print_query(cursor, query):
    cursor.execute(query)
    results = cursor.fetchall()
    for row in results:
        print str(row)


def exec_query(query, bool_return_prettytable=False):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:
            cur.execute("USE {0};".format(db_name))
            cur.execute(query)

            if bool_return_prettytable:
                results = from_db_cursor(cur)
            else:
                results = cur.fetchall()

            return results
    except Exception as err:
        print(str(err))
    finally:
        conn.commit()
        cur.close()
        conn.close()


def insert_test_results(NovaTestStats):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:

            # TODO: bugbugbug - all these queries should be a query string passed into a generic insert/update function
            cur.execute("USE {0};".format(db_name))
            sql_query = "INSERT INTO test_results(" \
                        "test_pass_id," \
                        "test_name," \
                        "concurrency_count," \
                        "time_started," \
                        "time_end," \
                        "time_total," \
                        "time_to_active," \
                        "time_to_ping," \
                        "time_to_ssh," \
                        "is_successful," \
                        "is_active," \
                        "is_pingable," \
                        "is_sshable, " \
                        "rps, " \
                        "hard_errors_exist, " \
                        "hard_error_count, " \
                        "soft_error_count) " \
                        " VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}','{7}','{8}',{9},{10},{11},{12}," \
                        "{13},{14},{15},{16})".format(NovaTestStats.test_pass_id,
                                                              NovaTestStats.test_name,
                                                              NovaTestStats.concurrency_count,
                                                              NovaTestStats.time_started,
                                                              NovaTestStats.time_ended,
                                                              NovaTestStats.time_total,
                                                              NovaTestStats.time_to_active,
                                                              NovaTestStats.time_to_ping,
                                                              NovaTestStats.time_to_ssh,
                                                              NovaTestStats.is_successful,
                                                              NovaTestStats.is_active,
                                                              NovaTestStats.is_ping_able,
                                                              NovaTestStats.is_ssh_able,
                                                              NovaTestStats.rps,
                                                              NovaTestStats.hard_errors_exist,
                                                              NovaTestStats.hard_error_count,
                                                              NovaTestStats.soft_error_count)

            print sql_query
            cur.execute(sql_query)
            int_test_id = cur.lastrowid
            conn.commit()

            sql_query = "INSERT INTO test_results_granular(" \
                        "test_id," \
                        "function_name," \
                        "time_started," \
                        "time_end," \
                        "time_total," \
                        "error_type," \
                        "error_text) VALUES"

            for NovaActionStat in NovaTestStats.nova_actions_list:

                sql_query += "('{0}','{1}','{2}'," \
                             "'{3}','{4}','{5}','{6}'),".format(int_test_id,
                                                                NovaActionStat.nova_action,
                                                                NovaActionStat.time_started,
                                                                NovaActionStat.time_ended,
                                                                NovaActionStat.time_total,
                                                                MySQLdb.escape_string(str(NovaActionStat.error_type)),
                                                                MySQLdb.escape_string(str(NovaActionStat.error_text)))

            sql_query = sql_query.rstrip(',')

            print sql_query
            cur.execute(sql_query)

            conn.commit()

    except Exception as err:
        print(str(err))
    finally:
        cur.close()
        conn.close()


def create_new_test_pass(NovaTestStats):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:

            cur.execute("USE {0};".format(db_name))
            sql_query = "INSERT INTO test_passes(" \
                        "test_pass_name," \
                        "environ_name," \
                        "zone," \
                        "region," \
                        "execution_hostname," \
                        "cloud_account_username," \
                        "time_started) " \
                        " VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}')".format(NovaTestStats.test_name,
                                                                              NovaTestStats.environ_name,
                                                                              NovaTestStats.zone,
                                                                              NovaTestStats.region,
                                                                              NovaTestStats.execution_host,
                                                                              NovaTestStats.cloud_account_username,
                                                                              NovaTestStats.time_started)
            print sql_query
            cur.execute(sql_query)
            int_pass_id = cur.lastrowid
            conn.commit()

            return int_pass_id

    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def update_test_pass(NovaTestStats):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:

            cur.execute("USE {0};".format(db_name))
            sql_query = "UPDATE test_passes " \
                        "SET time_end='{1}', " \
                        "time_total={2} " \
                        "WHERE test_pass_id={0}".format(NovaTestStats.test_pass_id,
                                                       NovaTestStats.time_ended,
                                                       NovaTestStats.time_total)

            print sql_query
            cur.execute(sql_query)
    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def test_add_test_pass():

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:

            cur.execute("USE {0};".format(db_name))

            # test adding a test case
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            stop_time = datetime.now() + timedelta(minutes=3)

            sql_query = "INSERT INTO test_passes(" \
                        "test_pass_name," \
                        "environ_name," \
                        "zone," \
                        "region," \
                        "execution_hostname," \
                        "cloud_account_username," \
                        "time_started," \
                        "time_end," \
                        "time_total," \
                        "hard_errors_exist) " \
                        " VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}'" \
                        ",'{7}','{8}','{9}')".format('manual-test-nova-boot-expo-scaling',
                                                                         'bravo',
                                                                         'az1',
                                                                         'region-a.geo-1',
                                                                         'matty.local',
                                                                         'hpcs.paas.cie@hp.com',
                                                                         start_time,
                                                                         stop_time,
                                                                         12,
                                                                         0)

            cur.execute(sql_query)

            test_id = cur.lastrowid

            conn.commit()

            print_query(cur, 'select * from test_passes')

            pass

            return test_id

    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def test_add_result_data(test_pass_id):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:

            cur.execute("USE {0};".format(db_name))

            # test adding a test case
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            stop_time = datetime.now() + timedelta(minutes=3)

            sql_query = "INSERT INTO test_results(" \
                        "test_pass_id," \
                        "test_name," \
                        "time_started," \
                        "time_end," \
                        "time_total," \
                        "time_to_active," \
                        "time_to_ping," \
                        "time_to_ssh," \
                        "is_successful," \
                        "is_active," \
                        "is_pingable," \
                        "is_sshable, " \
                        "rps, " \
                        "hard_errors_exist) " \
                        " VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}'," \
                        "'{7}','{8}','{9}','{10}','{11}','{12}','{13}')".format(int(test_pass_id),
                                                                            'manual_boot_test__matty',
                                                                            start_time,
                                                                            stop_time,
                                                                            12,
                                                                            3,
                                                                            3,
                                                                            4,
                                                                            5,
                                                                            1,
                                                                            1,
                                                                            1,
                                                                            2,
                                                                            1)

            print sql_query

            cur.execute(sql_query)

            test_id = cur.lastrowid

            conn.commit()

            print_query(cur, 'select * from test_results')

            pass

            return test_id

    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def test_add_result_data_granular(int_test_id):
    try:
        conn = get_mysql_connection()

        with conn:
            cur = conn.cursor()
            cur.execute("USE {0};".format(db_name))

            # test adding a test case
            test_insert_granular_data(conn, cur, 'connect', int_test_id)
            test_insert_granular_data(conn, cur, 'set_flavor', int_test_id)
            test_insert_granular_data(conn, cur, 'set_image', int_test_id)
            test_insert_granular_data(conn, cur, 'boot', int_test_id)
            test_insert_granular_data(conn, cur, 'wait_for_active_status', int_test_id)
            test_insert_granular_data(conn, cur, 'servers_get_list', int_test_id)
            test_insert_granular_data(conn, cur, 'servers_get_list', int_test_id)
            test_insert_granular_data(conn, cur, 'servers_get_list', int_test_id)
            test_insert_granular_data(conn, cur, 'nova_show_server', int_test_id)
            test_insert_granular_data(conn, cur, 'floating_ips_get_list', int_test_id)
            test_insert_granular_data(conn, cur, 'floating_ip_attach', int_test_id)
            test_insert_granular_data(conn, cur, 'ping_device', int_test_id)
            test_insert_granular_data(conn, cur, 'ssh', int_test_id)
            test_insert_granular_data(conn, cur, 'floating_ip_dettach', int_test_id)
            test_insert_granular_data(conn, cur, 'delete_server', int_test_id)

            print_query(cur, 'select * from test_results_granular')

    except Exception as err:
        print(str(err))

    finally:
        conn.commit()
        cur.close()
        conn.close()


def test_insert_granular_data(conn, cursor, func_name, int_test_id):

    rand_seconds = randint(1, 10)

    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stop_time = datetime.now() + timedelta(seconds=rand_seconds)

    sql_query = "INSERT INTO test_results_granular(" \
            "test_id," \
            "function_name," \
            "time_started," \
            "time_end," \
            "time_total) " \
            " VALUES('{0}','{1}','{2}','{3}','{4}')".format(int_test_id,
                                                      func_name,
                                                      start_time,
                                                      stop_time,
                                                      3)
    cursor.execute(sql_query)
    conn.commit()



if __name__ == '__main__':
    main()
