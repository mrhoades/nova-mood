from decimal import Decimal
import nova_mood_db


def expo_scaling_avg_time_to_x(environ_name, last_x_minutes):
    """ time to boot, active, ssh, total - try using data in stacked bar chart """

    sql_query = """
    select count(*) as total_nodes,
      concurrency_count,
      AVG(time_total) as avg_time_total,
      AVG(time_to_active) as avg_time_to_active,
      AVG(time_to_ping) as avg_time_to_ping,
      AVG(time_to_ssh) as avg_time_to_ssh,
      AVG(hard_errors_exist) as avg_error
    from test_results
    group by concurrency_count
    order by concurrency_count;
    """.format(environ_name, str(last_x_minutes))

    result = nova_mood_db.exec_query(sql_query)

    return result


def get_rps_for_environement(environ_name, last_x_minutes):

    sql_query = """
    select count(*)
    from test_results as r
    left join test_results_granular as rg on r.test_id = rg.test_id
    where r.environ_name = '{0}'
    and rg.time_started > DATE_SUB(NOW(), INTERVAL {1} minute);
    """.format(environ_name, str(last_x_minutes))

    result = nova_mood_db.exec_query(sql_query)
    nova_request_count = result[0][0]
    total_seconds = last_x_minutes*60

    rps = Decimal(nova_request_count)/Decimal(total_seconds)
    rps = round(rps, 2)

    return rps



# def get_rps_for_environement_old(environ_name, last_x_minutes):
#
#     sql_query = """
#     select count(*)
#     from test_results as r
#     left join test_results_granular as rg on r.test_id = rg.test_id
#     where r.environ_name = '{0}'
#     and rg.time_started > DATE_SUB(NOW(), INTERVAL {1} minute);
#     """.format(environ_name, str(last_x_minutes))
#
#     result = stats_db.exec_query(sql_query)
#     nova_request_count = result[0][0]
#     total_seconds = last_x_minutes*60
#
#     rps = Decimal(nova_request_count)/Decimal(total_seconds)
#     rps = round(rps, 2)
#
#     return rps
