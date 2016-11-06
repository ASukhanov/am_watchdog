#!/usr/bin/python -t
# Watchlist for am_watchdog
ParIn                           ,ParMin,ParMax,            ParOut,ParOk,ParFail = \
                               0,    1,     2,                  3,  4,    5#,  6,    7 #
watchlist = [('dac4140ChOppis.930-oppis2.B.4.outputS', 1.3, 0, 'lop.corrcl_set.outputS',  0,    1),
             ('ls2-discharge-ps.current.measurementM',   0, 15, 'ls2-cs.boiler.temp.setpointS',  2,    3)]

