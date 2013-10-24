import pygal
from decimal import Decimal
from dateutil import rrule
import nova_mood_db
from datetime import datetime
from datetime import timedelta

numdays = 100
base = datetime.today()
dateList = [base - timedelta(days=x) for x in range(0, numdays)]
mydatelist = list(rrule.rrule(rrule.DAILY, count=100, dtstart=datetime.now()))

print mydatelist
print dateList
pass


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
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
    group by my_date, tp.zone
    order by my_date;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


def failure_types_by_region(bool_prettytable=False):
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
    where tp.environ_name = 'bravo'
     and tp.time_started > DATE_SUB(NOW(), INTERVAL 90 day)
    group by my_date, tp.zone
    order by my_date;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


sql_result_data = failure_rates_by_zone(bool_prettytable=True)

print sql_result_data

sql_result_data = failure_rates_by_zone()

az1_data = []
az2_data = []
az3_data = []
prod1_az2_data = []

for index, row in enumerate(sql_result_data):

    date_object = datetime.strptime(row[0], '%m-%d-%Y')

    if row[1] == 'bravo' and row[2] == 'az1':
        az1_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'bravo' and row[2] == 'az2':
        az2_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'bravo' and row[2] == 'az3':
        az3_data.append([date_object, int(row[5] * 100)])
    elif row[1] == 'prod_1.0' and row[2] == 'az-2':
        prod1_az2_data.append([date_object, int(row[5] * 100)])


from pygal.style import NeonStyle
chart = pygal.DateY(style=NeonStyle,
                    width=1024,
                    height=768,
                    x_label_rotation=90,
                    truncate_label=12,
                    show_dots=False)

# chart = pygal.DateY(style=NeonStyle,
#                     tooltip_border_radius=4,
#                     tooltip_font_size=12,
#                     width=1024,
#                     height=768,
#                     x_label_rotation=90,
#                     y_label_rotation=10,
#                     truncate_label=12,
#                     show_dots=False,
#                     dots_size=1)

chart.title = 'US East - Failure Rate by Zone - Last 90 Days'

chart.add('useast-az1', az1_data)
chart.add('useast-az2', az2_data)
chart.add('useast-az3', az3_data)
# chart.add('uswest-az2', prod1_az2_data)

chart.render_to_file('us-east-failure-rate.svg')
chart.render_to_png('us-east-failure-rate.png')
