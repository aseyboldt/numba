#! /usr/bin/env python
# ______________________________________________________________________
'''
Test type mapping.
'''
# ______________________________________________________________________

import numba
from numba import *
from numba.decorators import jit
from numba.tests import test_support

import unittest

# ______________________________________________________________________

def if1(arg): # stupid nosetests
    if arg > 0:
        result = 22
    else:
        result = 42
    return result

def if2(arg):
    if arg > 0:
        result = 22
    else:
        result = 42
    return result

# ______________________________________________________________________

class TestIf(test_support.ByteCodeTestCase):
    def test_int(self):
        func = self.jit(restype=numba.int_,
                                 argtypes=[numba.int_])(if1)
        self.assertEqual(func(-1), 42)
        self.assertEqual(func(1), 22)

    def test_long(self):
        func = self.jit(restype=numba.long_,
                                 argtypes=[numba.long_])(if2)
        self.assertEqual(func(-1), 42)
        self.assertEqual(func(1), 22)
# ______________________________________________________________________

class TestASTIf(test_support.ASTTestCase, TestIf):
    pass

if __name__ == "__main__":
    unittest.main()

# ______________________________________________________________________
# End of test_if.py

