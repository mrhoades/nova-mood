import pygal
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



# stacked_bar = pygal.StackedBar(rounded_bars=10)
# stacked_bar.title = 'Browser usage evolution (in %)'
# stacked_bar.x_labels = map(str, range(2002, 2013))
# stacked_bar.add('Firefox', [None, None, 0, 16.6,   25,   31, 36.4, 45.5, 46.3, 42.8, 37.1])
# stacked_bar.add('Chrome',  [None, None, None, None, None, None,    0,  3.9, 10.8, 23.8, 35.3])
# stacked_bar.add('IE',      [85.8, 84.6, 84.7, 74.5,   66, 58.6, 54.7, 44.8, 36.2, 26.6, 20.1])
# stacked_bar.add('Others',  [14.2, 15.4, 15.3,  8.9,    9, 10.4,  8.9,  5.8,  6.7,  6.8,  7.5])
# stacked_bar.render_to_file('stacked_bar_chart.svg')
# stacked_bar.render_to_png('stacked_bar_chart.png')




