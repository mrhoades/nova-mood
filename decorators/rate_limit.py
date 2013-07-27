import time


def rate_limit(max_per_second):
    min_interval = 1.0 / float(max_per_second)

    def decorate(func):
        time_last_called = [0.0]

        def rate_limit_function(*args, **kwargs):
            timeNow = time.clock()
            time_elapsed = timeNow - time_last_called[0]
            time_to_wait = min_interval - time_elapsed

            if time_to_wait > 0:
                print 'time_to_wait: ' + str(time_to_wait)
                time.sleep(time_to_wait)
                pass
            ret = func(*args, **kwargs)
            time_last_called[0] = time.clock()
            return ret
        return rate_limit_function
    return decorate


@rate_limit(4)
def test_rate_limit(int_num):
    print str(int_num)


if __name__ == "__main__":

    for i in range(1, 100):

        test_rate_limit(i)