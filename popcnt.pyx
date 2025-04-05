"""
Compile with gcc flag -mpopcnt
"""
import numpy as np
cimport numpy as np
cimport cython
from libc.stdint cimport uint32_t, uint8_t, int16_t

cdef extern int __builtin_popcount(unsigned int) nogil

@cython.boundscheck(False)
@cython.wraparound(False)
cdef uint32_t _inplace_popcount_32_2d(uint32_t[:] arr) nogil:
    cdef int i
    cdef uint32_t total = 0

    total = 0

    for i in xrange(arr.shape[0]):
        total += __builtin_popcount(arr[i])

    return total

@cython.boundscheck(False)
@cython.wraparound(False)
cdef void _create_samples(uint32_t[:] data, double[:] samples, uint32_t[:] byte_samples, uint32_t[:] bit_times, uint8_t[:] bits, int clr_length, int set_length, double sample_len) nogil:
    cdef int i
    cdef int j
    cdef int k
    cdef int l
    cdef int p = 0
    cdef int steps

    for i in xrange(data.shape[0]):
        for j in xrange(4):
            for k in xrange(8):
                steps = set_length if ((data[i] >> (j*8 + k)) & 1) else clr_length

                for l in xrange(steps):
                    samples[p + l] = -10000
                    samples[p + steps + l] = 10000

                bit_times[i*32 + j*8 + k] = int(p * sample_len)
                bits[i*32 + j*8 + k] = (data[i] >> (j*8 + k)) & 1

                p += 2*steps

            byte_samples[i*4 + j] = p

@cython.boundscheck(False)
@cython.wraparound(False)
cdef void _create_tone(double[:] samples, int length) nogil:
    cdef int i
    cdef int j

    for i in xrange(samples.shape[0]//(length*2)):
        for j in xrange(length):
            samples[i*length*2 + j]     = -10000
            samples[i*length*2 + length + j] = 10000

def count_array(arr):
    return _inplace_popcount_32_2d(arr)

def create_samples(data, samples, byte_samples, bit_times, bits, clr_length, set_length, sample_len):
    _create_samples(data, samples, byte_samples, bit_times, bits, clr_length, set_length, sample_len)

def create_tone(samples, length):
    _create_tone(samples, length)
