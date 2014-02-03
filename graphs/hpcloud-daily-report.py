import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import pygal
from pygal.style import NeonStyle
import nova_mood_db
from datetime import datetime


def failure_rates_by_day_envs(bool_prettytable=False, for_the_last_x_days=90):
    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
        select DATE_FORMAT(t.time_started, '%Y-%m-%d') as my_date,
          tp.environ_name,
          count(*) as total_tests,
          SUM(hard_errors_exist) as total_failures,
          AVG(t.hard_errors_exist) as failure_rate
        from test_results as t
        join test_passes as tp on tp.test_pass_id = t.test_pass_id
         and tp.time_started > DATE_SUB(NOW(), INTERVAL {0} day)
        group by my_date, tp.environ_name
        order by my_date desc;
        """.format(for_the_last_x_days)

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result



################################################
########### GENERATE ALL ENVS GRAPH - Failure Rate By Day
################################################

sql_result_data = failure_rates_by_day_envs(for_the_last_x_days=360)

bravo_east_data = []
bravo_west_data = []
prod_10_data = []

for index, row in enumerate(sql_result_data):

    date_object = datetime.strptime(row[0], '%Y-%m-%d')

    if row[1] == 'bravo':
        bravo_east_data.append([date_object, int(row[4] * 100)])
    elif row[1] == 'bravo-AW2-2':
        bravo_west_data.append([date_object, int(row[4] * 100)])
    elif row[1] == 'prod_1.0':
        prod_10_data.append([date_object, int(row[4] * 100)])


from pygal.style import NeonStyle
chart = pygal.DateY(style=NeonStyle,
                    width=1024,
                    height=768,
                    x_label_rotation=90,
                    truncate_label=12,
                    show_dots=False)

chart.title = 'HP Cloud Envs - % Failure Rate by Day - Last 360 Days'

chart.add('Bravo East', bravo_east_data)
chart.add('Bravo West', bravo_west_data)
chart.add('One Dot Zero', prod_10_data)

chart.render_to_file('prod-envs-failure-rate-by-day.svg')
chart.render_to_png('prod-envs-failure-rate-by-day.png')

