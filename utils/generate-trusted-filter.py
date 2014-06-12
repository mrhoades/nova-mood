from datetime import datetime
from random import randint
from datetime import timedelta
from prettytable import from_db_cursor

import MySQLdb

db_name = 'reviewdb'
db_root_user = 'root'
db_password = 'Rnetpa55'
db_hostname_or_ip = '15.185.94.144'


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


def generate_trusted_filter(bool_prettytable=False):

    """ get failure counts, rate, grouped by day, for each zone """

    sql_query = """
    select id1.account_id, id1.email_address, id1.external_id, id2.external_id, acc.full_name
      from (select account_id, external_id, email_address from account_external_ids where external_id like '%login.launchpad.net%') as id1
      left join (select account_id, external_id from account_external_ids where external_id like '%/launchpad.net%') as id2 on id1.account_id = id2.account_id
      left join (select account_id, external_id from account_external_ids where external_id like '%username:%') as id3 on id1.account_id = id3.account_id
      left join (select * from accounts) as acc on id1.account_id = acc.account_id
    where acc.inactive = 'N'
    order by acc.full_name
    """

    # create output strings that look like this pattern
    # trustedOpenID = ^https://(login\\.)?launchpad\\.net/(~damian-curry|\\+id/nzJLDpT)$

    result = exec_query(sql_query, bool_prettytable)

    for identity in result:
        email = str(identity[1])
        lp_user = str(identity[2]).replace('https://login.launchpad.net/', '')
        lp_user_code = str(identity[3]).replace('https://launchpad.net/', '')
        trust = 'trustedOpenID = ^https://(login\\\.)?launchpad\\\.net/({0}|\\\{1}|{2})$'.format(lp_user_code, lp_user, email)
        print trust

generate_trusted_filter()



