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
              and tp.environ_name = 'bravo-AW2-2'
              and tp.time_started > DATE_SUB(NOW(), INTERVAL 7 day)
              and trg.error_type != '(HTTP 404) Resource Not Found'
              and trg.error_type not like '%unsupported operand type(s) for%'
        group by tp.environ_name, trg.error_type
        order by tp.environ_name, func_error_count desc) as error_type_counts;
    """

    result = nova_mood_db.exec_query(sql_query, bool_prettytable)

    return result


sql_result_data = failure_type_counts(bool_prettytable=True)

print sql_result_data
