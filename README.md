
*** Nova Mood Still Under Construction ***

Thanks to jesusaurus for a ton of nova_service_test.py code. It was a huge chunk of excellent clay to start with!


Nova Mood Synopsis

1) Provide nova action metrics database (setup script included)

2) Provide analysis queries

3) Provides python-novaclient wrapper with nova_collect decorator that:

    -- throttles requests, to smooth out request flow
    -- retry with exponential back off
        -- this keeps things going when we get rate-limited
    -- collect metrics for every request that is made
       -- wrap atomic nova actions
       -- wrap parent actions (which contain several atomic actions)
    -- collect any error that is encountered
        -- collect soft errors (like rate-limiting) and keep going
        -- collect hard errors (like 500) and keep going if possible
        -- collect timeout errors when vm cannot be pinged or ssh'd to
    -- synchronize requests
        -- if env needs it (currently bravo is happier)
        -- if nova env works with sync, fails without sync, concurrency is a problem

4) All nova request actions are tagged with date time, so concurrent (multi-account) metrics can be collected
    -- it's important to know what tests are going on where and when, to make the result data set more intelligible


CONFIGURE:

1) configure settings, nova auth, db_auth, and scaling settings in config.yaml

-- really, the default config.yaml should require only setting the nova account info.

0) setup a nova_mood MySQL database by running nova_mood_db.py script


RUN:
python controller.py



TODO: bugbugbug - write more detailed notes about how to configure and run this stuff




