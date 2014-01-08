import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from time import sleep
from datetime import datetime
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
        order by tp.environ_name;
        """ % for_the_last_x_days

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    print ''
    print '**********************************'
    print '***  Failure Rates - %s Days  ***' % for_the_last_x_days
    print '***********************************'
    print result

    return result


# def failure_rate_moving_avg(bool_prettytable=False, moving_avg_period=30, for_the_last_x_days=10):
#
#     for i in reversed(range(for_the_last_x_days)):
#
#         date_range_start = i + moving_avg_period
#         date_range_end = i
#
#         sql_query = """
#             select tp.environ_name,
#               AVG(t.hard_errors_exist) as failure_rate
#             from test_results as t
#             join test_passes as tp on tp.test_pass_id = t.test_pass_id
#             where tp.time_started > DATE_SUB(NOW(), INTERVAL %s day)
#              and tp.time_started < DATE_SUB(NOW(), INTERVAL %s day)
#              and tp.environ_name = 'bravo'
#             group by tp.environ_name
#             order by tp.environ_name desc;
#             """ % (date_range_start, date_range_end)
#
#         result = nova_mood_db.exec_query(sql_query, bool_prettytable)
#
#         print '%s Moving AVG - ' % result + 'Failure rate %s days ago, from the %s days prior...' % (date_range_end, date_range_start)
#
#         print nova_mood_db.exec_query("select DATE_SUB(NOW(), INTERVAL %s day)" % date_range_start, bool_prettytable)
#         print nova_mood_db.exec_query("select DATE_SUB(NOW(), INTERVAL %s day)" % date_range_end, bool_prettytable)
#
#         print str(datetime.now())
#
#         date_object = datetime.strptime(datetime.now(), '%m-%d-%Y-%H')
#
#         print date_object
#
#         sleep(.2)
#
#     return result
#
# failure_rate_moving_avg(moving_avg_period=10, for_the_last_x_days=7)



failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=7)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=14)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=30)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=90)
failure_rates_by_env(bool_prettytable=True, for_the_last_x_days=360)

