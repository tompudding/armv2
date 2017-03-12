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
cdef void _create_samples(uint32_t[:] data, double[:] samples, int clr_length, int set_length) nogil:
    cdef int i
    cdef int j
    cdef int k
    cdef int p = 0
    cdef int steps
    
    for i in xrange(data.shape[0]):
        for j in xrange(32):
            steps = set_length if ((data[i] >> j) & 1) else clr_length

            for k in xrange(steps):
                samples[p + k] = -10000
                samples[p + steps + k] = 10000

            p += 2*steps

def count_array(arr):
    return _inplace_popcount_32_2d(arr)

def create_samples(data, samples, clr_length, set_length):
    _create_samples(data, samples, clr_length, set_length)