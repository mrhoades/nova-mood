import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import pygal
from pygal.style import NeonStyle
from datetime import datetime
import nova_mood_db


def failure_rates_by_zone(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
    select DATE_FORMAT(t.time_started, '%Y-%m-%d-%H') as my_date,
      tp.environ_name,
      tp.zone,
      count(*) as total_tests,
      SUM(hard_errors_exist) as total_failures,
      AVG(t.hard_errors_exist) as failure_rate
    from test_results as t
    join test_passes as tp on tp.test_pass_id = t.test_pass_id
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
    where tp.environ_name = 'paas-racks-east'
    group by my_date, tp.environ_name, tp.zone
    order by my_date desc;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_rates_by_day_zone(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
    select DATE_FORMAT(t.time_started, '%Y-%m-%d') as my_date,
      tp.environ_name,
      tp.zone,
      count(*) as total_tests,
      SUM(hard_errors_exist) as total_failures,
      AVG(t.hard_errors_exist) as failure_rate
    from test_results as t
    join test_passes as tp on tp.test_pass_id = t.test_pass_id
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
    group by my_date, tp.environ_name, tp.zone
    order by my_date desc;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_rates_by_hour_zone(bool_prettytable=False):
    """ get failure counts, rate, grouped by hour, for each zone """

    sql_query = """
    select DATE_FORMAT(t.time_started, '%Y-%m-%d-%H') as my_date,
      tp.environ_name,
      tp.zone,
      count(*) as total_tests,
      SUM(hard_errors_exist) as total_failures,
      AVG(t.hard_errors_exist) as failure_rate
    from test_results as t
    join test_passes as tp on tp.test_pass_id = t.test_pass_id
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 30 day)
    group by my_date, tp.environ_name, tp.zone
    order by my_date desc;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_type_counts(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
        select * from (select count(*) as func_error_count,
          tp.environ_name,
          trg.error_type
        from test_results as tr
        left join test_results_granular as trg on tr.test_id = trg.test_id
        left join test_passes as tp on tr.test_pass_id = tp.test_pass_id
        where error_type != ''
              and tp.environ_name = 'paas-racks-east'
              and tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
              and trg.error_type != '(HTTP 404) Resource Not Found'
              and trg.error_type != '(HTTP 429) Rate Limited'
              and trg.error_type not like '%unsupported operand type(s) for%'
        group by tp.environ_name, trg.error_type
        order by tp.environ_name, func_error_count desc) as error_type_counts;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_type_counts_by_nova_call_concurrency(bool_prettytable=False):
    """ get failure counts, """

    sql_query = """
        select count(*) as error_count,
          #tp.environ_name,
          trg.function_name,
          tr.concurrency_count,
          trg.error_type
        from test_results as tr
        left join test_results_granular as trg on tr.test_id = trg.test_id
        left join test_passes as tp on tr.test_pass_id = tp.test_pass_id
        where tr.concurrency_count > 1
          and tp.environ_name = 'paas-racks-east'
          and trg.error_type != ''
          and tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
          and trg.error_type != '(HTTP 404) Resource Not Found'
          and trg.error_type != '(HTTP 429) Rate Limited'
          and trg.error_type not like '%unsupported operand type(s) for%'
        group by tr.concurrency_count, trg.function_name, trg.error_type
        order by error_count desc
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_type_by_hour_last_seven_days(bool_prettytable=False):
    """ failure type by hour - last seven days """

    sql_query = """
    select DATE_FORMAT(tr.time_started, '%Y-%m-%d-%H') as my_date, count(*) as error_count,
      tp.zone,
      trg.function_name,
      tr.concurrency_count,
      trg.error_type
    from test_results as tr
    left join test_results_granular as trg on tr.test_id = trg.test_id
    left join test_passes as tp on tr.test_pass_id = tp.test_pass_id
    where tr.concurrency_count >= 1
      and tp.environ_name = 'paas-racks-east'
      and trg.error_type != ''
      and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
      and trg.error_type != '(HTTP 404) Resource Not Found'
      and trg.error_type != '(HTTP 429) Rate Limited'
      and trg.error_type not like '%unsupported operand type(s) for%'
    group by my_date, tp.zone, trg.error_type, tr.concurrency_count
    order by my_date desc, error_count desc;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_rates_by_zone_and_concurrency(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
    select count(*) as total_booted,
      tp.environ_name,
      tp.zone,
      tp.cloud_account_username,
      t.concurrency_count,
      AVG(NULLIF(t.time_total,0)) as avg_time_total,
      AVG(NULLIF(t.time_to_active,0)) as avg_time_to_active,
      AVG(NULLIF(t.time_to_ping,0)) as avg_time_to_ping,
      AVG(NULLIF(t.time_to_ssh,0)) as avg_time_to_ssh,
      AVG(t.hard_errors_exist) as pct_error
    from test_results as t
    left join test_passes as tp on tp.test_pass_id = t.test_pass_id
    where tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
      and tp.environ_name = 'paas-racks-east'
    group by tp.environ_name, tp.zone, t.concurrency_count
    order by t.concurrency_count, tp.zone;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result

def unpingable_ips(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
        select DATE_FORMAT(tr.time_started, '%Y-%m-%d') as my_date,
          SUBSTRING(trg.error_text, INSTR(trg.error_text, 'for IP ') + 7, INSTR(trg.error_text, 'after trying for') - INSTR(trg.error_text, 'for IP ') - 7) as bad_ip,
          count(*) as ip_used_x_times,
          tp.environ_name,
          tp.zone,
          trg.error_type
        from test_results as tr
        left join test_results_granular as trg on tr.test_id = trg.test_id
        left join test_passes as tp on tr.test_pass_id = tp.test_pass_id
        where trg.error_type = 'Ping Timeout'
          and tp.environ_name = 'paas-racks-east'
              and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
        group by my_date, bad_ip
        order by my_date desc, tp.environ_name;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result



print '*********************************************************'
print '*** PaaS Racks East - Failure Rate By Day and Zone ***'
print '*********************************************************'
sql_result_data = failure_rates_by_zone(bool_prettytable=True)
print sql_result_data

print ''
print '*******************************************************************************'
print '*** PaaS Racks East - Failure Counts - 7 Day - By Hour Zone Method and Concurrency Count'
print '*******************************************************************************'
sql_result_data = failure_type_by_hour_last_seven_days(bool_prettytable=True)
print sql_result_data

print ''
print '*****************************************************************'
print '*** PaaS Racks East - Failure By Zone and Concurrency Count ***'
print '*****************************************************************'
sql_result_data = failure_rates_by_zone_and_concurrency(bool_prettytable=True)
print sql_result_data

print ''
print '*****************************************************************'
print '*** PaaS Racks East - Instance IPs Not Pingable (after 10 minutes) - Last 7 Days ***'
print '*****************************************************************'
sql_result_data = unpingable_ips(bool_prettytable=True)
print sql_result_data


################################################
########### GENERATE GRAPH - Failure Rate by Hour and Zone - Last 30 Days
################################################

sql_result_data = failure_rates_by_hour_zone()

az1_data = []
az2_data = []
az3_data = []
az1_sl390_data = []

for index, row in enumerate(sql_result_data):

    date_object = datetime.strptime(row[0], '%Y-%m-%d-%H')

    if row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az1-v1':
        az1_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az2-v1':
        az2_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az3-v1':
        az3_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az1-sl390':
        az1_sl390_data.append([date_object, int(row[5] * 100)])

chart = pygal.DateY(style=NeonStyle,
                    width=1024,
                    height=768,
                    x_label_rotation=90,
                    truncate_label=16,
                    show_dots=False)

chart.title = 'PaaS Racks East - % Failure Rate by Hour and Zone - Last 30 Days'

# dbaas-ae1az1-v1
# dbaas-ae1az2-v1
# dbaas-ae1az3-v1
#

chart.add('dbaas-ae1az1-v1', az1_data)
chart.add('dbaas-ae1az2-v1', az2_data)
chart.add('dbaas-ae1az3-v1', az3_data)
chart.add('ae1az1-sl390', az1_sl390_data)

chart.render_to_file('paas-racks-east-failure-rate-by-hour.svg')
chart.render_to_png('paas-racks-east-failure-rate-by-hour.png')


################################################
########### GENERATE GRAPH - Failure Rate By Day
################################################

sql_result_data = failure_rates_by_day_zone()

az1_data = []
az2_data = []
az3_data = []
az1_sl390_data = []

for index, row in enumerate(sql_result_data):

    date_object = datetime.strptime(row[0], '%Y-%m-%d')

    if row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az1-v1':
        az1_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az2-v1':
        az2_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az3-v1':
        az3_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'paas-racks-east' and row[2] == 'dbaas-ae1az1-sl390':
        az1_sl390_data.append([date_object, int(row[5] * 100)])

chart = pygal.DateY(style=NeonStyle,
                    width=1024,
                    height=768,
                    x_label_rotation=90,
                    truncate_label=12,
                    show_dots=False)

chart.title = 'PaaS Racks East AE1 - % Failure Rate by Day - Last 90 Days'

chart.add('dbaas-ae1az1-v1', az1_data)
chart.add('dbaas-ae1az2-v1', az2_data)
chart.add('dbaas-ae1az3-v1', az3_data)
chart.add('ae1az1-sl390', az1_sl390_data)

chart.render_to_file('paas-racks-east-failure-rate-by-day.svg')
chart.render_to_png('paas-racks-east-failure-rate-by-day.png')


