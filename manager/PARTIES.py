#!/usr/bin/python

from time import sleep
import random
import sys
import os
import collections
import threading
#sys.path.append('/home/sc2682/scripts/monitor')
#from monitorN import startMonitoring, endMonitoring
import subprocess
import get_qos_metrics

xrange = range

CONFIG = 'config.txt' # default path to the input config.txt file
if (len(sys.argv) > 1):
    CONFIG = sys.argv[1]

# QoS target of each application, in nanoseconds.
QOS = {"moses": 15000000, "xapian": 5000000, "nginx": 10000000, "sphinx": 2500000000, "memcached": 600000, "mongodb": 300000000}

NUM_PLUS_ONE = 20
INTERVAL  = 0.1  # Frequency of monitoring, unit is second
TIMELIMIT = 200   # How long to run this controller, unit is in second. 
REST      = 100
NUM       = 0    # Number of colocated applications
APP       = [None for i in xrange(NUM_PLUS_ONE)] # Application names
QoS       = [None for i in xrange(NUM_PLUS_ONE)] # Target QoS of each application
ECORES    = [i for i in range(0,32,1)] # unallocated cores
CORES     = [None for i in xrange(NUM_PLUS_ONE)] # CPU allocation
LOAD      = []                        
FREQ      = [2200 for i in xrange(NUM_PLUS_ONE)] # Frequency allocation
EWAY      = 0                          # unallocated ways
WAY       = [0 for i in xrange(NUM_PLUS_ONE)]    # Allocation of LLC ways
Lat       = [0 for i in xrange(NUM_PLUS_ONE)]    # Real-time tail latency
MLat      = [0 for i in xrange(NUM_PLUS_ONE)]    # Real-time tail latency of a moving window
Slack     = [0 for i in xrange(NUM_PLUS_ONE)]    # Real-time tail latency slack 
LSlack    = [0 for i in xrange(NUM_PLUS_ONE)]    # Real-time tail latency slack in the last interval
LLSlack   = [0 for i in xrange(NUM_PLUS_ONE)]    # Real-time tail latency slack in the last interval
LDOWN     = [0 for i in xrange(NUM_PLUS_ONE)]    # Time to wait before this app can be downsized again
CPU       = [0 for i in xrange(NUM_PLUS_ONE)]    # CPU Utilization per core of each application
cCPU      = collections.deque(maxlen=(int(5.0/INTERVAL)))
MEM       = [0 for i in xrange(NUM_PLUS_ONE)]    # Total memory bandwidth usage of each application
State     = [0 for i in xrange(NUM_PLUS_ONE)]    # FSM State during resource adjustment
rLat      = [[] for i in xrange(NUM_PLUS_ONE)]   # Save real-time latency for final plotting
rrLat     = [[] for i in xrange(NUM_PLUS_ONE)]   # Save real-time latency for final plotting
rCORES    = [[] for i in xrange(NUM_PLUS_ONE)]   # Save real-time #cores for final plotting
rWAY      = [[] for i in xrange(NUM_PLUS_ONE)]   # Save real-time #ways for final plotting
rFREQ     = [[] for i in xrange(NUM_PLUS_ONE)]   # Save real-time frequency for final plotting
FF        = open("gabage.txt", "w")    # random outputs
FT        = open("gabage2.txt", "w")   # other random outputs
PLOT      = True                       # If needed to do the final plotting 
saveEnergy= True                       # If needed to save energy when QoSes can all be satisfied
helpID    = 0                          # Application ID that is being helped. >0 means upSize, <0 means Downsize
victimID  = 0                          # Application that is helping helpID, thus is a innocent victim
TOLERANCE = 5                          # Check these times of latency whenver an action is taken

def init():
    global EWAY, MLat, TIMELIMIT, CONFIG, NUM, APP, QoS, Lat, Slack, ECORES, CORES, FREQ, WAY, CPU, MEM, INTERVAL
    if len(sys.argv) > 2: 
        TIMELIMIT = int(sys.argv[2])
# Read the name of colocated applications and their QoS target (may be in different units)
    print("initialize!")
    if os.path.isfile('%s' % CONFIG) == False:
        print("config file (%s) does not exist!" % CONFIG)
        exit(0)
    with open('%s' % CONFIG, 'r') as f:
        lines = f.readlines()
        assert len(lines[0].split()) == 1
        NUM = int(lines[0].split()[0])
        assert len(lines) >= (NUM + 1)
        for i in range(1, NUM+1, 1):
            words = lines[i].split()
            assert len(words) == 2
            CORES[i] = []
            APP[i]   = words[0]
            #assert APP[i] in QOS
            QoS[i]   = int(words[1]) * 1.0
            WAY[i]   = 20/NUM
            MLat[i]  = collections.deque(maxlen=(int(1.0/INTERVAL)))
# Initialize resource parititioning
    j = 0
    while len(ECORES) > 0:
        CORES[j+1].append(ECORES.pop())
        j = (j + 1) % NUM
    for i in xrange(20-20//NUM*NUM):
        WAY[i+1] += 1

# Enforce harware isolation
    propogateCore()
    # Monitoring of CPU and cache utilizataion is not needed in PARTIES manager. You can comment them out. These are just legacy codes and may be useful if you want to monitor real-time resource usage.
    # monproc = subprocess.Popen("python /home/sc2682/scripts/monitor/monitorN.py %d" % TIMELIMIT, shell=True, stdout=FF, stderr=FF, preexec_fn=os.setsid);

def main():
    global TIMELIMIT
    init()
    print("after initiation...")
    sleep(1)
    currentTime = 0
    while True:
        #wait()
        makeDecision()

def makeDecision():
    global Lat, LSlack, TOLERANCE, LLSlack, REST, Slack, NUM, FREQ, helpID, victimID;
    print ("Make a decision! ", helpID)
    if helpID > 0:
        cur = Lat[helpID]
        cnt = 0
        for i in xrange(TOLERANCE):
            wait()
            if Lat[helpID] < cur:
                cnt += 1
            else:
                cnt -= 1
        if cnt <= 0 or (State[helpID] == 2 and FREQ[helpID] == 2300):
            #return revert(helpID)
            revert(helpID)
       # else:
       #     cnt = 0
       #     wait()
       #     while (Lat[helpID] < cur):
       #         cur = Lat[helpID]
       #         wait()
        helpID = victimID = 0
    elif helpID < 0:
        cur = Lat[-helpID]
        cnt = 0
        for i in xrange(TOLERANCE):
            wait()
            flag = True
            for j in range(1, NUM+1):
                if (Slack[j] < 0.05):
                    flag = False
                    break
            if flag == False:
                cnt -= 1
            else:
                cnt += 1
        if cnt <= 0:
            #return revert(-helpID)  # Revert back as it doesn't benefit from this resource
            revert(helpID)
          #  wait()
            cnt = 0
            for i in xrange(TOLERANCE):
                wait()
                flag = True
                for j in range(1, NUM+1):
                    if (Slack[j] < 0.05):
                        flag = False
                        break
                if flag == False:
                    cnt -= 1
                else:
                    cnt += 1
            if cnt <= 0: 
                for i in xrange(TOLERANCE):
                    wait()
          #  while Slack[-helpID] < 0 or LSlack[-helpID] < 0:
          #      print "wait..."
          #      wait()
        helpID = victimID = 0
    else:
        wait()
    if helpID == 0:                 # Don't need to check any application before making a new decision
        idx = -1
        victimID = 0
        for i in range(1, NUM+1):   # First find if any app violates QoS
            if Slack[i] < 0.05 and LSlack[i] < 0.05:
                if idx == -1 or LSlack[i] < LSlack[idx]:
                    idx = i
            elif (LDOWN[i] == 0) and Slack[i] > 0.2 and LSlack[i] > 0.2 and (victimID == 0 or Slack[i] > Slack[victimID]):
                victimID = i
        if idx != -1:
            return upSize(idx)             # If found, give more resources to this app
        elif saveEnergy == True and victimID > 0:    # If not found, try removing resources
            return downSize(victimID)
        else:
            wait()
    return True


# FSM state of resource adjustment
# -3: give it fewer cache
# -2: give it fewer frequency
# -1: give it fewer cores
#  0: not in adjustment 
#  1: give it more cores
#  2: give it more frequency
#  3: give it more cache

def nextState(idx, upsize=True):
    global State
    if State[idx] == 0:
        if upsize == True:
            State[idx] = random.randint(1, 3)
        else:
            State[idx] = -random.randint(1, 3)
    elif State[idx] == -1:
        State[idx] = -2
    elif State[idx] == -2:
        State[idx] = -1
    elif State[idx] == 1:
        State[idx] = 2
    elif State[idx] == 2:
        State[idx] = 1
    else:
        assert False

def revert(idx):
    global State, APP, helpID, victimID, REST
    print(idx, " revert back")
    if idx < 0:
        if State[-idx] == -1:
            assert adjustCore(-idx, 1, False) == True
        elif State[-idx] == -2:
            assert adjustFreq(-idx, 1) == True
        # elif State[-idx] == -3:
            # assert adjustCache(-idx, 1, False) == True
        else:
            assert False;
        nextState(-idx)
        LDOWN[-idx] = REST
    else:
        nextState(idx)
    return True

def upSize(idx):
    global State, helpID, victimID, APP
    victimID = 0
    helpID = idx
    print("Upsize ", APP[idx], "(",State[idx],")")
    if State[idx] <= 0:
        State[idx] = random.randint(1,2)           
    for k in xrange(3):
        if (State[idx] == 1 and adjustCore(idx, 1, False) == False) or \
           (State[idx] == 2 and adjustFreq(idx, 1) == False) or \
           (State[idx] == 3 and adjustCache(idx, 1, False) == False):
                nextState(idx);
        else:
            return True
    print("No way to upsize any more...")
    helpID = 0
    return False

def downSize(idx):
    global State, helpID, victimID
    print("Downsize ", APP[idx], "(",State[idx],")")
    victimID = 0
    if State[idx] >= 0:
        State[idx] = -random.randint(1,2)                   
    for k in xrange(3):
        if (State[idx] == -1 and adjustCore(idx, -1, False) == False) or \
           (State[idx] == -2 and adjustFreq(idx, -1) == False) or \
           (State[idx] == -3 and adjustCache(idx, -1, False) == False):
                nextState(idx);
        else:
            helpID = -idx
            return True
    return False

def wait():
    global INTERVAL, TIMELIMIT
    sleep(INTERVAL)
    for i in xrange(1, NUM+1):
        if LDOWN[i] > 0:
            LDOWN[i] -= 1
    getLat()
    getData()
    record()
    if TIMELIMIT != -1:
        TIMELIMIT -= INTERVAL
        if TIMELIMIT < 0:
            printout()
            exit(0)

def getLat():
    global APP, Lat, MLat, LLSlack, LSlack, Slack, QoS, NUM

    for i in xrange(1, NUM+1):
        app = APP[i]
        # if APP[i][-1] == "2":
        # app = APP[i][:-1] The fuck
        # p = subprocess.Popen("curl http://%s:84/%s/0.txt | tail -1" % (IP[i], app), shell=True, stdout=subprocess.PIPE, stderr=FF, preexec_fn=os.setsid,bufsize=0);
        # out, err = p.communicate()
        out = get_qos_metrics.get_99p_latency_for_server(app)
        LLSlack[i] = Slack[i]
        #if out!='' and (not ('html' in out)):
        Lat[i] = int(out)
        MLat[i].append(int(out))
        LSlack[i] = 1-sum(MLat[i])*1.0/len(MLat[i])/QoS[i]
        #LSlack[i] = Slack[i]
        Slack[i] = (QoS[i] - Lat[i])*1.0 / QoS[i]
        print('  --', APP[i],':', Lat[i], '(', Slack[i], LSlack[i],')')

def getData():
    global NUM, cCPU, CPU, CORES, MEM
    tmp = 0

def coreStr(cores):
    return ','.join(str(e) for e in cores)

def coreStrHyper(cores):
    return coreStr(cores) + ',' + ','.join(str(e + 44) for e in cores)

def way(ways, rightways):
    return hex(int('1'*ways+'0'*rightways,2))

def adjustCore(idx, num, hasVictim):
    global State, CORES, Slack, ECORES, victimID
    if num < 0:
        if len(CORES[idx]) <= -num:
            return False
        if hasVictim == False or victimID == 0:
            for i in xrange(-num):
                ECORES.append(CORES[idx].pop())
        else:
            for i in xrange(-num):
                CORES[victimID].append(CORES[idx].pop())
            propogateCore(victimID)
    else:
        assert num == 1 and hasVictim == False
        if len(ECORES) >= 1:
            CORES[idx].append(ECORES.pop())
        else:
            victimID = 0
            for i in xrange(1, NUM+1):
                if i!=idx and len(CORES[i]) > 1 and (victimID == 0 or Slack[i] > Slack[victimID]):
                    victimID = i
            if victimID == 0:
                return False
            CORES[idx].append(CORES[victimID].pop())
            if State[idx] == State[victimID]:
                nextState(victimID)
            propogateCore(victimID)
    propogateCore(idx)
    return True

def adjustFreq(idx, num):
    global FREQ, APP, State
    assert FREQ[idx] >=1200 and FREQ[idx] <= 2300
    if num < 0:
        if FREQ[idx] == 1200:
            return False       # Frequency is already at the lowest. Cannot be reduced further
        else:
            FREQ[idx] += 100*num
            propogateFreq(idx)
    else:
        if FREQ[idx] == 2300:
            return False       # Shuang
            victimID = 0
            for i in xrange(1, NUM+1):
                if i!=idx and FREQ[i] > 1200 and (victimID == 0 or Slack[i] > Slack[victimID]):
                    victimID = i
            if victimID == 0:
                return False
            else:
                FREQ[victimID] -= 100*num
                propogateFreq(victimID)
                if State[victimID] == State[idx]:
                    nextState(victimID)
        else:
            FREQ[idx] += 100*num
            propogateFreq(idx)
    return True

def adjustCache_(idx, num, hasVictim):
    global WAY, EWAY, NUM, victimID, State, Slack
    if num < 0:
        if WAY[idx] <= -num:
            return False
        if hasVictim == False or victimID == 0:
            EWAY -= num
        else:
            WAY[victimID] -= num
            propogateCache(victimID)
    else:
        assert num == 1 and hasVictim == False
        if EWAY > 0:
            EWAY -= 1
        else:
            victimID = 0
            for i in xrange(1, NUM+1):
                if i!=idx and WAY[i]>1 and (victimID == 0 or Slack[i] > Slack[victimID]):
                    victimID = i
            if victimID == 0:
                return False
            WAY[victimID] -= num
            propogateCache(victimID)
            if State[idx] == State[victimID]:
                nextState(victimID)
    WAY[idx] += num
    propogateCache(idx)
    return True

def propogateCore(idx=None):
    global APP, CORES, NUM
    if idx == None:
        for i in xrange(1, NUM+1):
            print('    Change Core of', APP[i],':',CORES[i] , get_qos_metrics.SERVER_TO_FULL_ID[APP[i]])
            subprocess.run(['sudo', 'docker', 'update', '--cpuset-cpus', coreStr(CORES[i]), get_qos_metrics.SERVER_TO_FULL_ID[APP[i]]], stdout=FT, stderr=FT)
        #propogateCache()
        propogateFreq()
    else:
        subprocess.run(['sudo', "docker", "update", "--cpuset-cpus", coreStr(CORES[idx]), get_qos_metrics.SERVER_TO_FULL_ID[APP[idx]]], stdout=FF, stderr=FF)
        print('    Change Core of', APP[idx],':',CORES[idx] )
        #propogateCache(idx)
        propogateFreq(idx)

def propogateCache(idx=None):
    global CORES, WAY, NUM, APP
    ways = 0
    for i in xrange(1, NUM+1):
        if idx == None or i >= idx:
            subprocess.call(["pqos", "-e", "llc:%d=%s;" % (i+1, way(WAY[i], ways))], stdout=FF, stderr=FF)
            subprocess.call(["pqos", "-a", "llc:%d=%s;" % (i+1, coreStrHyper(CORES[i]))], stdout=FF,stderr=FF)
        if idx == None or i == idx:
            print('    Change Cache Ways of', APP[i],':',WAY[i])
        ways += WAY[i]

def propogateFreq(idx=None):
    global CORES, FREQ, NUM, APP
    if idx == None:
        subprocess.call(['sudo', "cpupower", "-c", "0-31", "frequency-set", "-g", "userspace"], stdout=FT, stderr=FT)
        print('sudo', "cpupower", "-c", "0-31", "frequency-set", "-g", "userspace")
        subprocess.call(['sudo', "cpupower", "-c", "0-31", "frequency-set", "-f", "2200MHz"], stdout=FT, stderr=FT)
        for i in xrange(1, NUM+1):
            print('    Change Frequency of', APP[i],':',FREQ[i])
            if FREQ[i] <= 2200:
                subprocess.call(['sudo', "cpupower", "-c", coreStrHyper(CORES[i]), "frequency-set", "-f", "%dMHz" % FREQ[i]], stdout=FT, stderr=FT)
            else:
                subprocess.call(['sudo', "cpupower", "-c", coreStrHyper(CORES[i]), "frequency-set", "-g", "performance"], stdout=FT, stderr=FT)
    else:
        print('    Change Frequency of', APP[idx],':',FREQ[idx])
        if FREQ[idx] <= 2200:
            subprocess.call(['sudo', "cpupower", "-c", coreStrHyper(CORES[idx]), "frequency-set", "-g", "userspace"],stdout=FT, stderr=FT)
            print('sudo', "cpupower", "-c", coreStrHyper(CORES[idx]), "frequency-set", "-g", "userspace")
            subprocess.call(['sudo', "cpupower", "-c", coreStrHyper(CORES[idx]), "frequency-set", "-f", "%dMHz" % FREQ[idx]], stdout=FT, stderr=FT)
        else:
            subprocess.call(['sudo', "cpupower", "-c", coreStrHyper(CORES[idx]), "frequency-set", "-g", "performance"], stdout=FT, stderr=FT)


# Fuck this function. We don't care about recording, just use the wrk data. It's good enough tbh.
def record():
    global CPU, LOAD, NUM, Lat, rrLat, saveEnergy, rLat, CORES, rCORES, WAY, rWAY, FREQ, rFREQ
    # for i in xrange(1, NUM+1):
    #     rrLat[i].append(Lat[i])
    #     rLat[i].append(1-LSlack[i])
    #     rCORES[i].append(len(CORES[i]))
    #     rWAY[i].append(WAY[i])
    #     rFREQ[i].append(FREQ[i])
    # p = subprocess.Popen("curl http://128.253.128.66:84/memcached/count.txt | tail -1", shell=True, stdout=subprocess.PIPE, stderr=FF, preexec_fn=os.setsid,bufsize=0);
    # #LOAD.append(10)
    # out, err = p.communicate()
    # if out!='':
    #     LOAD.append(int(out)-1)
    #     #if int(out) > 24:
    #     #    saveEnergy = False
    #     #else:
    #     #    saveEnergy = True
    # elif len(LOAD) > 0:
    #     LOAD.append(LOAD[-1])
    # else:
    #     LOAD.append(0)
    
def printout():
    global NUM, rrLat, LOAD, rLat, rCORES, cCPU, rFREQ, rWAY
    print("CPU Utilization: ", sum(cCPU)*1.0/len(cCPU))
    if PLOT == True:
        of=open("results.txt", "w")
        for i in xrange(1, NUM+1):
            for item in rrLat[i]:
                of.write("%d " % item)
            of.write("\n")
            for item in rLat[i]:
                of.write("%f " % item)
            of.write("\n")
            for item in rCORES[i]:
                of.write("%d " % item)
            of.write("\n")
            for item in rFREQ[i]:
                of.write("%d " % item)
            of.write("\n")
            for item in rWAY[i]:
                of.write("%d " % item)
            of.write("\n")
        for item in LOAD:
            of.write("%d " % item)
        of.write("\n")
        of.close()

if __name__ == "__main__":
    main()






