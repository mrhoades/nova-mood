import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

import nova_mood_db


def failure_rates_by_env(bool_prettytable=False, for_the_last_x_days=360):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
        select count(*) as total_booted,
          tp.environ_name,
          AVG(t.hard_errors_exist) as pct_error
        from test_results as t
        left join test_passes as tp on tp.test_pass_id = t.test_pass_id
        where tp.time_started > DATE_SUB(NOW(), INTERVAL %s day)
        group by tp.environ_name
        order by t.concurrency_count, tp.zone;
        """ % for_the_last_x_days

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    print ''
    print '*********************************************************'
    print '***  Failure Rates - %s Days  ***' % for_the_last_x_days
    print '*********************************************************'
    print result

    return result


failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=7)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=14)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=30)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=90)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=360)

