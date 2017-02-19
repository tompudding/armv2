import os
import sys
import random

#First grab the seed

with open('hdr.h', 'rb') as f:
    for line in f:
        if line.startswith('#define SEED'):
            seed = int(line.split()[2])
            break
    else:
        raise SystemExit('Failed to find seed')

output, input = sys.argv[1:]

data = []
with open(input, 'rb') as f:
    for line in f:
        line_data = line.strip().strip(',').split(',')
        if not all(item.startswith('0x') for item in line_data):
            continue
        data.extend([int(item,16) for item in line_data])

#Now encrypt that badger
random.seed(seed)
for i in xrange(len(data)):
    data[i] ^= (random.getrandbits(32) & 0xff)
#Apparently a 0 goes on the end

#Now to put that in a header file format
with open(output, 'wb') as f:
    f.write('char data_file[] = {\n')
    for i in xrange(0, len(data), 16):
        part = data[i:i+16]
        f.write(','.join( (('0x%02x' % b) for b in part) ))
        f.write(',\n')
    f.write('0};\n');
