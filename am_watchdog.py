#!/usr/bin/python -t
# Watchdog ADO manager
#__version__ = 'v01 2016-10-28'# Created, no ado manager yet. Getting multiple parameters.
#__version__ = 'v02 2016-11-01' # minMax, okFail
#__version__ = 'v04 2016-11-02' # from cad import
#__version__ = 'v06 2016-11-02' # Lots of mods: LifeS, LifeM, reset, sysName-dependend watchlist.
#__version__ = 'v07 2016-11-05'  # Stop: Restart.
__version__ = 'v08 2016-11-07'  # Moving average added.


mgrName = 'am_watchdog'

sysName = 'watchdog_default'
#sysName = 'watchdog_OPPIS'

#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
# Watchlist
#
ParIn, ParMin, ParMax, ParLife, ParOut, ParTripS = 0,1,2,3,4,5

if sysName == 'watchdog_OPPIS':
    #import watchlist_OPPIS as wl
    watchlist = [('dac4140ChOppis.930-oppis2.B.4:outputS', 1.3, 0, 1, 'None',  1),
                 ('ls2-discharge-ps.current.measurementM',   0,15, 1, 'None',  3),
                 (                                     '',   0, 0, 0, 'None',  0),
                 (                                     '',   0, 0, 0, 'None',  0)]

else: # Default watchlist for am_watchdog
    #import watchlist as wl
    watchlist = [('simple.test:sinM', -0.5,    0.5,    1  ,'am_simple.0:monM_0',  1),
                 ('simple.test:degM',   30,    180,    1  ,              'None',  2),
                 (                '',    0,      0,    0  ,              'None',  0),
                 (                '',    0,      0,    0  ,              'None',  0)]
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

import sys
import time
import threading

# cadops-related classes
from cad import cns
inform = False # debugging of cns
from cad import am
am.debug = True # debugging of am

class MovingAverage:
    def __init__(self,width):
        self.list = [0 for x in range(width)]
        self.ma = 0.
        self.width = float(width)
    def __call__(self,xx):
        self.ma -= self.list.pop()/self.width
        self.ma += xx/self.width
        self.list.insert(0,xx)
        return self.ma

class ParSetter:
    '''This class is needed to redirect parameter setting function back to AMWatchdog.'''
    def __init__(self,amw,index):
        self.amw = amw
        self.index = index
    def parInSet(self): self.amw.parInSet(self.index)
    def parAverageSet(self): self.amw.parAverageSet(self.index)
    def parOutSet(self): self.amw.parOutSet(self.index)
    def parReset(self): self.amw.parReset(self.index)
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
server = None
#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
class AMWatchdog:
    def __init__(self,dbg=0):
        #'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
        self.paused = False
        
        self.version = am.adoParameter("version", 'StringType', 1, 0,
            cns.Feature.CONFIGURATION | cns.Feature.READABLE,__version__)

        self.statusM = am.adoParameter("statusM", 'StringType', 1, 0, cns.Feature.DIAGNOSTIC, '')
        self.statusM.add("desc", "status")
            
        self.commandS = am.adoParameter("stopS", 'StringType', 1, 0,
                                     cns.Feature.DISCRETE | cns.Feature.WRITABLE|cns.Feature.EDITABLE,"Pause")
        self.commandS.add("desc", "Pause, Continue, Server exit")
        self.commandS.add("legalValues", "Pause,Continue,Exit,Restart")
        self.commandS.set = self.command_set

        self.resetS = am.adoParameter('ResetS', 'StringType', 1, 0,
            cns.Feature.DISCRETE | cns.Feature.WRITABLE|cns.Feature.EDITABLE,"Trips")
        self.resetS.add("desc", "reset all parameters")
        self.resetS.add("legalValues", "Trips,Init")
        self.resetS.set = self.reset

        self.sleepS = am.adoParameter("sleepS", 'DoubleType', 1, 0,
            cns.Feature.WRITABLE|cns.Feature.EDITABLE, 1)
        self.sleepS.add("desc", "sleep time [s] between checks")

        self.dbg = dbg
        self.dbgS = am.adoParameter("debugS", 'IntType', 1, 0,
            cns.Feature.WRITABLE|cns.Feature.EDITABLE|cns.Feature.DIAGNOSTIC, self.dbg)
        self.dbgS.add("desc", "debug flag, bit0 for debugging am.py, the rest for self")
        self.dbgS.set = self.dbgSet
        self.dbgSet()

        self.countM = am.adoParameter("countM", 'IntType', 1, 0,cns.Feature.DIAGNOSTIC,0)
        self.countM.add("desc", "check counter")
        self.initPars()
        
    def initPars(self):
        self.dictAdoGet = {}        # dictionary of requests for cns.adoGet
        self.requestsAdoSet = []    # requests for cns.adoSet
        self.parsetter = []         # ParSetter classes
        self.parInS = []            # ado:parameter names of input parameters
        self.parInM = []            # current values of parIn's
        self.parAverageS = []       # ado:parameter names of input parameters
        self.ma = []                # moving average class of the parIn
        self.parMinS = []           # minimums of tolerance intervals
        self.parMaxS = []           # maximums of tolerance intervals
        self.parOutS = []           # ado:parameter names of output parameters
        self.parOutM = []           # current values of parOut's
        self.parLifeM = []          # numbers of allowed failures until parameter trips
        self.parLifeS = []          # reset values or parLifeS
        self.parTripS = []          # trip values for parOut's
        self.parResetS = []         # reset buttons
        ii = 0
        #'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
        for item in watchlist:
            #if item[ParIn] == '': continue
            self.parsetter.append(ParSetter(self,ii)) # append parameter setter class

            # add input (watched) parameter
            #self.dictAdoGet.append([None,'','value'])
            self.parInS.append(am.adoParameter('parInS_'+str(ii), 'StringType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParIn]))
            self.parInS[ii].add('desc','ado:parameter name of the parameter to watch')
            self.parInS[ii].set = self.parsetter[ii].parInSet
            self.parInSet(ii)           

            # add current value of the watched parameter
            self.parInM.append(am.adoParameter('parInM_'+str(ii), 'DoubleType', 1, 0,0,0))
            self.parInM[ii].add('desc','current value of the watched parameter')
            
            self.parAverageS.append(am.adoParameter('parAverageS_'+str(ii), 'DoubleType', 1, 0,0,1))
            self.parAverageS[ii].add('desc','width of the averaging window')
            self.parAverageS[ii].set = self.parsetter[ii].parAverageSet
            
            # add minimum of the tolerance interval
            self.parMinS.append(am.adoParameter('parMinS_'+str(ii), 'DoubleType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParMin]))
            self.parMinS[ii].add('desc','minimum of the tolerance interval')
            
            # add max of the tolerance interval
            self.parMaxS.append(am.adoParameter('parMaxS_'+str(ii), 'DoubleType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParMax]))
            self.parMaxS[ii].add('desc','maximum of the tolerance interval')

            self.parOutM.append(am.adoParameter('parOutM_'+str(ii), 'StringType',1,0,0,'Undefined'))
            self.parOutM[ii].add('desc','current value of parOut, None if not set.')

            self.requestsAdoSet.append([None,'','value',0.])
            self.parOutS.append(am.adoParameter('parOutS_'+str(ii), 'StringType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParOut]))
            self.parOutS[ii].add('desc','output parameter, which will be tripped, depending on parInM')
            self.parOutS[ii].set = self.parsetter[ii].parOutSet
            self.parOutSet(ii)
            
            self.parTripS.append(am.adoParameter('parTripS_'+str(ii), 'DoubleType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParTripS]))
            self.parTripS[ii].add('desc',"trip value to be set to parOut when parIn trips")
            
            self.parLifeS.append(am.adoParameter('parLifeS_'+str(ii), 'DoubleType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, item[ParLife]))
            self.parLifeS[ii].add('desc',"number of allowed failures until parameter trips")            

            self.parLifeM.append(am.adoParameter('parLifeM_'+str(ii), 'DoubleType', 1, 0,
                cns.Feature.WRITABLE|cns.Feature.EDITABLE, 0))
            self.parLifeM[ii].add('desc',"number of failures left until parameter trips")            

            self.parResetS.append(am.adoParameter('parReset_'+str(ii), 'VoidType', 1, 0,
                cns.Feature.WRITABLE | cns.Feature.READABLE | cns.Feature.EDITABLE,None))
            self.parResetS[ii].add("desc", "reset tripped parameter")
            self.parResetS[ii].set = self.parsetter[ii].parReset
            self.parReset(ii)

            # all done
            ii += 1
        #,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
        if self.dbg&4: print('requestsAdoGets:'+str(self.dictAdoGet))
        if self.dbg&4: print('requestsAdoSets:'+str(self.requestsAdoSet))

    def dbgSet(self):
        self.dbg = self.dbgS.value.value
        print('debug set to '+str(self.dbg))
        am.debug = self.dbg & 1
        if am.debug: print('am debugging enabled')

    def parInSet(self,ind):
        #if self.dictAdoGet[ind][0] != None : 
        #    print('ado['+str(ind)+'] have been initiated. TODO: delete it.')
        try:    
            del self.dictAdoGet[str(ind)]
        except: 
            pass
        string = self.parInS[ind].value.value
        print 'parInSet',string
        adoIn = None
        try:
            aname,pname = self.parInS[ind].value.value.rsplit(':', 1)
            adoIn = cns.CreateAdo(aname)
            if adoIn == None:
                msg = 'ERROR: creating input ADO '+aname+')'
                print(msg)
                self.update_status(msg)
                #if server: server.run = False
                #sys.exit(3)
        except Exception, e:
            msg = 'WARNING. '+str(self.parInS[ind].name)+' will not be watched. '+str(e)
            self.update_status(msg)
            print(msg)
        if adoIn:
            self.parAverageSet(ind)
            self.dictAdoGet[str(ind)] = [adoIn,pname,'value']
            if self.dbg&4: print('requestGet['+str(ind)+'] added')
            
    def parAverageSet(self,ind):
        self.ma[ind] = MovingAverage(self.parAverageS[ind].value.value)        

    def parOutSet(self,ind):
        if self.requestsAdoSet[ind][0] != None : 
            print('rewriting request['+str(ind)+'].')
        ss = self.parOutS[ind].value.value
        adoOut,pname = None, 'None'
        try:
            if str(ind) in self.dictAdoGet:
                aname,cname = ss.rsplit(':', 1)
                adoOut = cns.CreateAdo(aname) 
                if adoOut != None: 
                    pname = cname
                else:
                    msg = 'ERROR: creating ADO for '+self.parOutS[ind].name
                    print(msg)
                    self.update_status(msg)
                    #if server: server.run = False
                    #sys.exit(4)
        except Exception, e:
            msg = 'WARNING. '+str(self.parInS[ind].name)+' will not be tripped. '+str(e)
            self.update_status(msg)
            print(msg)
        if adoOut:
            self.parOutM[ind].value.value = 'None'
        else:
            self.parOutM[ind].value.value = 'Undefined'
        self.parOutM[ind].updateValueTimestamp()
        self.requestsAdoSet[ind][0],self.requestsAdoSet[ind][1] = adoOut,pname
        if self.dbg&4: print('requestsAdoSet list('+str(ind)+') = '+str([adoOut,pname]))

    def parReset(self,ind):
        if self.dbg&2: print('resetting '+str(ind))
        self.parLifeM[ind].value.value = self.parLifeS[ind].value.value
        self.parLifeM[ind].updateValueTimestamp()
        #self.parOutM[ind].value.value = 'None'
        #self.parOutM[ind].updateValueTimestamp()
        
    def reset(self):
        prev_paused = self.paused
        self.paused = True
        if self.resetS.value.value == 'Init':    
            if self.dbg&4: print('current requestsAdoGets:'+str(self.dictAdoGet))
            self.initPars()
        else:      
            for ii in range(len(self.parLifeM)):
                self.parReset(ii)
        self.update_status('')
        self.paused = prev_paused

    def command_set(self):
        cmd = self.commandS.value.value
        if self.dbg&2: print('commandS: '+str(cmd))
        if cmd == 'Exit': sys.exit(0)
        elif cmd == 'Restart': sys.exit(99)
        elif cmd == 'Pause': self.paused = True
        elif cmd == 'Continue':
            self.update_status('')
            self.paused = False
        
    def update_status(self, text):
        self.statusM.value.value = text
        self.statusM.updateValueTimestamp()
        
    def process_data(self):
        # 
        self.countM.setTimestamps()
        self.countM.updateValueTimestamp()

        if self.paused: return
        data = cns.adoGet(list = self.dictAdoGet.values())
        indexes = [int(ii) for ii in self.dictAdoGet.keys()]
        if self.dbg&4: print('process_data:'+str(self.countM.value.value))
        for ii in range(len(data)):
            idx = indexes[ii]
            vv = data[ii][0]
            vv = self.ma[idx](vv)) # moving average of the value
            self.parInM[idx].value.value = vv
            self.parInM[idx].updateValueTimestamp()  # update current parameter value
            #vo = None
            if self.parMinS[idx].value.value < vv < self.parMaxS[idx].value.value and self.parLifeM[idx].value.value:
                # parameter is good
                if self.parOutM[idx].value.value != 'OK' and self.requestsAdoSet[idx][0]:
                    self.parOutM[idx].value.value = 'OK'
                    self.parOutM[idx].updateValueTimestamp()
                pass
            else:
                # deal with parameter failure
                if self.parLifeM[idx].value.value: 
                    self.parLifeM[idx].value.value -=1
                    self.parLifeM[idx].updateValueTimestamp()
                    if self.dbg&2: print('par '+self.parInM[idx].name+' failed, lives left:'+str(self.parLifeM[idx].value.value))
                    pass
                else:
                    # parameter tripped. 
                    vo = self.parTripS[idx].value.value
                    if self.dbg&2: print('parameter '+self.parInM[idx].name+' tripped, setting out to '+str(vo))
                    if self.dbg&8: print('setting '+self.parOutM[idx].name+' to '+str(vo))
                    if self.requestsAdoSet[idx][0]:
                        self.requestsAdoSet[idx][3] = vo
                        if self.dbg&8: print('adoSet request: '+str(self.requestsAdoSet[idx]))
                        try:
                            rc = cns.adoSet(list = [self.requestsAdoSet[idx]])
                        except Exception, e:
                            msg = 'ERROR: in adoSet('+str(self.requestsAdoSet[idx][0])+'): '+str(e)
                            if self.dbg&2: print(msg)
                            vo = 'ERROR'
                             #TODO: handle disconnects properly
                            #server.run = False
                            #sys.exit(5) 
                        if self.dbg&8: print('Updating value '+str(self.parOutM[idx].name)+'='+str(vo))
                        self.parOutM[idx].value.value = str(vo)
                        self.parOutM[idx].updateValueTimestamp()                
            
        self.countM.value.value += 1
        self.countM.updateValueTimestamp()
        pass   
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
#   Main
#
if __name__ == "__main__":
    dbg = 0            
    args = sys.argv[1:]
    while len(args) > 0:
        if args[0] == '-debug':
            args.pop(0)
            dbg = 0x2 | 0x4 | 0x8
    amw = AMWatchdog(dbg)

    #'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    # Thread functions
    def process_thread(the_amw):
        while True:
            the_amw.process_data()            
            time.sleep(the_amw.sleepS.value.value)
        print('process_thread finished')
    # Start everything
    process_thread_update = threading.Thread(target=process_thread, args=(amw,))
    process_thread_update.daemon = True
    process_thread_update.start()
    try:
      server = am.adoServer( mgrName )
    except:
      print('ERROR: constructing server '+mgrName+', check if it is configured in fecManager.')
      sys.exit(1)
    amw.server = server
    #TODO: It would be useful to inform user which ADO to look for. 
    adoName = 'watchdog.0' # defined in fecManager
    print('Service '+mgrName+', sysName:'+sysName+', version:'+__version__+' started, to control it: adoPet '+adoName)
    try:
        server.loop()
    except KeyboardInterrupt:
        pass
    finally:
        server.unregister()
        server.HBrun = False
        print 'Service '+mgrName+' stopped.'
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

