import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

import nova_mood_db


def failure_rates_by_zone(bool_prettytable=False):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
    select DATE_FORMAT(t.time_started, '%m-%d-%Y') as my_date,
      tp.environ_name,
      tp.zone,
      count(*) as total_tests,
      SUM(hard_errors_exist) as total_failures,
      AVG(t.hard_errors_exist) as failure_rate
    from test_results as t
    join test_passes as tp on tp.test_pass_id = t.test_pass_id
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
    where tp.environ_name = 'bravo'
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
              and tp.environ_name = 'bravo'
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
          and tp.environ_name = 'bravo'
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
    -- failure type by hour last seven days
    select DATE_FORMAT(tr.time_started, '%m-%d-%Y-%H') as my_date, count(*) as error_count,
      #tp.environ_name,
      trg.function_name,
      tr.concurrency_count,
      trg.error_type
    from test_results as tr
    left join test_results_granular as trg on tr.test_id = trg.test_id
    left join test_passes as tp on tr.test_pass_id = tp.test_pass_id
    where tr.concurrency_count > 1
      and tp.environ_name = 'bravo'
      and trg.error_type != ''
      and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
      and trg.error_type != '(HTTP 404) Resource Not Found'
      and trg.error_type != '(HTTP 429) Rate Limited'
      and trg.error_type not like '%unsupported operand type(s) for%'
    group by my_date, trg.error_type, tr.concurrency_count
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
      and tp.environ_name = 'bravo'
    group by tp.environ_name, tp.zone, t.concurrency_count
    order by t.concurrency_count, tp.zone;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result

print '*********************************************************'
print '*** Bravo East AE1 Failure Rate By Day and Zone ***'
print '*********************************************************'
sql_result_data = failure_rates_by_zone(bool_prettytable=True)
print sql_result_data

print ''
print '*******************************************************************************'
print '*** Bravo East AE1 Failure Counts - 7 Day - By Hour Method and Concurrency Count'
print '*******************************************************************************'
sql_result_data = failure_type_by_hour_last_seven_days(bool_prettytable=True)
print sql_result_data

print ''
print '*****************************************************************'
print '*** Bravo East AE1 Failure By Zone and Concurrency Count ***'
print '*****************************************************************'
sql_result_data = failure_rates_by_zone_and_concurrency(bool_prettytable=True)
print sql_result_data

