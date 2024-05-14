import get_qos_metrics
import subprocess

xrange = range

CONFIG = 'config.txt' # default path to the input config.txt file
APP       = [None for i in xrange(20)] # Application names
ECORES    = [i for i in range(0,32,1)] # unallocated cores

def coreStr(cores):
    return ','.join(str(e) for e in cores)

with open('%s' % CONFIG, 'r') as f:
    lines = f.readlines()
    assert len(lines[0].split()) == 1
    NUM = int(lines[0].split()[0])
    assert len(lines) >= (NUM + 1)
    subprocess.call(['sudo', "cpupower", "-c", "0-31", "frequency-set", "-g", "userspace"])
    subprocess.call(['sudo', "cpupower", "-c", "0-31", "frequency-set", "-f", "2400MHz"])
    # subprocess.call(['sudo', "cpupower", "-c", "0-31", "frequency-set", "-g", "performance"])
    for i in range(1, NUM+1, 1):
            words = lines[i].split()
            assert len(words) == 2
            APP[i]   = words[0]
            subprocess.run(['sudo', 'docker', 'update', '--cpuset-cpus', coreStr(ECORES), get_qos_metrics.SERVER_TO_FULL_ID[APP[i]]]) # lol + https://github.com/moby/moby/issues/41946
