#!/usr/bin/python -t
# Watchlist for am_watchdog
ParIn                           ,ParMin,ParMax,            ParOut,ParOk,ParFail = \
                               0,    1,     2,                  3,  4,    5#,  6,    7 #
watchlist = [('simple.test.sinM', -0.5, 0.5, 'am_simple.0.monM_0',  0,    1),
             ('simple.test.degM',   30, 180, 'am_simple.0.monM_1',  2,    3)]

