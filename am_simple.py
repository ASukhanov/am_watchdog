#!/usr/bin/python -t
# Example of a simple ado manager, based on am. 
#__version__ = 'v01 2016-11-01' # monM monitors added
#__version__ = 'v01 2016-11-02' # 'from cad import'
__version__ = 'v02 2016-11-05' # monM_ parameters editable

import sys
import time
import threading
import math 

from cad import am
from cad import cns

mgrName = 'am_simple'

if __name__ == "__main__":

    am.debug = False

    args = sys.argv[1:]
    while len(args) > 0:
        if args[0] == '-debug':
            args.pop(0)
            am.debug = True

    version = am.adoParameter("version", 'StringType', 1, 0,
        cns.Feature.CONFIGURATION | cns.Feature.READABLE,__version__)

    mydata = am.adoParameter("mydata", 'IntType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,101010)
    mydata.add("desc", "my int parameter")
    mydata.add("units", "wishes")
    mydata.add("timestamps", 0)

    mystringdata = am.adoParameter("mysdata", 'StringType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,"Hello")
    mystringdata.add("desc", "my string parameter")

    debugparam = am.adoParameter("debug", 'IntType', 1, 0,
        cns.Feature.WRITABLE|cns.Feature.READABLE|cns.Feature.EDITABLE|cns.Feature.DIAGNOSTIC,am.debug)
    debugparam.add("desc", "set debug flag")
    def debugparam_set(): am.debug = debugparam.value.value; print("set debug to"+str(am.debug))
    debugparam.set = debugparam_set

    degMparam = am.adoParameter("degM", 'IntType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,0)
    degMparam.add("desc", "angle")
    degMparam.add("units", "degree")
    degMparam.add("timestamps", 0)

    sinMparam = am.adoParameter("sinM", 'DoubleType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,0)
    sinMparam.add("desc", "angle")
    sinMparam.add("units", "degree")
    sinMparam.add("timestamps", 0)
    
    monM_0 = am.adoParameter("monM_0", 'DoubleType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,0)
    monM_0.add("desc", "monitor 0")
    def monM_0Set(): monM_0.updateValueTimestamp()# ; print('monM_0 set to '+str(monM_0.value.value))
    monM_0.set = monM_0Set

    monM_1 = am.adoParameter("monM_1", 'DoubleType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,0)
    monM_1.add("desc", "monitor 1")
    def monM_1Set(): monM_1.updateValueTimestamp()# ; print('monM_1 set to '+str(monM_1.value.value))
    monM_1.set = monM_1Set

    exitparam = am.adoParameter("exit", 'VoidType', 1, 0,
        cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,None)
    exitparam.add("desc", "set will stop manager")
    exitparam.set = lambda : sys.exit(0)
#''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    def parameter_increment( parameter ):
        value_property = parameter.value
        while True:
            time.sleep(.1)
            value_property.value = (value_property.value + 1)%360
            parameter.setTimestamps()
            parameter.updateValueTimestamp()

    def parameter_calc_sin( input_parameter, output_parameter):
        while True:
            time.sleep(1)
            output_parameter.value.value =  math.sin(input_parameter.value.value / 180. * 3.1415926)
            output_parameter.setTimestamps()
            output_parameter.updateValueTimestamp()

    mydata_update = threading.Thread(target=parameter_increment, args=(mydata,))
    mydata_update.daemon = True
    mydata_update.start()

    degMparam_update = threading.Thread(target=parameter_increment, args=(degMparam,))
    degMparam_update.daemon = True
    degMparam_update.start()

    sinMparam_update = threading.Thread(target=parameter_calc_sin, args=(degMparam,sinMparam,))
    sinMparam_update.daemon = True
    sinMparam_update.start()

    try:
      s = am.adoServer( mgrName )
    except:
      print('ERROR costructing server '+mgrName+', check if it is configured in fecManager.')
      sys.exit()
    print('Service '+mgrName+' started')
    try:
        s.loop()
    except KeyboardInterrupt:
        pass
    finally:
        s.unregister()
        s.HBrun = False
        print('Service '+mgrName+' stopped.')

