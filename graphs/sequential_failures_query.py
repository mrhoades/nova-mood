import MySQLdb
import optparse
import sys

# parse args
parser = optparse.OptionParser()
parser.add_option("-n", "--job-name",
                  dest="job_name",
                  action="store",
                  help="Name of the job that will be queried",
                  default='cieng-test-sequential-failures-alert')

parser.add_option("-f", "--failure-thresh",
                  dest="int_sequential_failure_threshold",
                  action="store",
                  help="Sequential failure threshold... fail if met or exceeded.",
                  default=3)

parser.add_option("-i", "--db-hostname-ip",
                  dest="db_hostname_or_ip",
                  action="store",
                  help="Database name that has the jenkins job audit data",
                  default='15.185.94.52')

parser.add_option("-d", "--db-name",
                  dest="db_name",
                  action="store",
                  help="Database name that has the jenkins job audit data",
                  default='jenkins_paas_audit_db')

parser.add_option("-u", "--db-username",
                  dest="db_user",
                  action="store",
                  help="Username that will be used to query the database",
                  default='my-db-user')

parser.add_option("-p", "--db-password",
                  dest="db_password",
                  action="store",
                  help="DB password that will be used to connect to database")

(options, args) = parser.parse_args()
if not options.db_password:
    print "ERROR please provide credential information for connecting to the job audit database."
    parser.print_help()
    sys.exit(0)

def check_for_sequential_failures(job_name, int_sequential_failure_threshold):
    """ look for seqential failures """

    sql_query = "select count(*) from (select * from JENKINS_BUILD_DETAILS " \
                "where name = '{0}' order by endDate DESC LIMIT {1}) as jobdata " \
                "where jobdata.result = 'FAILURE';".format(job_name, int_sequential_failure_threshold)

    result = exec_query(sql_query)

    return result


def get_mysql_connection(user=options.db_user,
                         password=options.db_password,
                         hostname_or_ip=options.db_hostname_or_ip):
    return MySQLdb.connect(hostname_or_ip, user, password)


def print_query(cursor, query):
    cursor.execute(query)
    results = cursor.fetchall()
    for row in results:
        print str(row)


def exec_query(query):

    conn = get_mysql_connection()
    cur = conn.cursor()

    try:
        with conn:
            cur.execute("USE {0};".format(options.db_name))
            cur.execute(query)
            results = cur.fetchall()
            return results
    except Exception as err:
        print(str(err))
    finally:
        conn.commit()
        cur.close()
        conn.close()


sql_result_data = check_for_sequential_failures(options.job_name, options.int_sequential_failure_threshold)

print 'THRESHOLD: ' + str(options.int_sequential_failure_threshold)

print 'RESULT COUNT: ' + str(sql_result_data[0][0])

if sql_result_data[0][0] >= options.int_sequential_failure_threshold:
    print 'SEQUENTIAL FAILURES DETECTED'
    url_of_pain = "FAILING JOB: {0}job/{1}".format('$JENKINS_URL', options.job_name)
    print url_of_pain
else:
    print 'NOTHING TO SEE HERE'
