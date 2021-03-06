#! /usr/bin/env python
# ______________________________________________________________________
'''test_mandelbrot

Test the Numba compiler on several variants of Mandelbrot set membership
computations.
'''
# ______________________________________________________________________

from numba.decorators import jit, autojit

import unittest

import numpy as np

import __builtin__

# ______________________________________________________________________

@autojit
def mandel(real_coord, imag_coord, max_iters):
    '''Given a the real and imaginary parts of a complex number,
    determine if it is a candidate for membership in the Mandelbrot
    set given a fixed number of iterations.
    Inspired by code at http://wiki.cython.org/examples/mandelbrot
    '''
    # Ideally we'd want to use a for loop, but we'll need to be able
    # to detect and desugar for loops over range/xrange/arange first.
    i = 0
    z_real = 0.
    z_imag = 0.
    while i < max_iters:
        z_real_n = z_real * z_real - z_imag * z_imag + real_coord
        z_imag = 2. * z_real * z_imag + imag_coord
        z_real = z_real_n
        if (z_real * z_real + z_imag * z_imag) >= 4:
            return i
        i += 1
    return -1

mandel_1c = jit(backend='bytecode',
                argtypes = ['d', 'd', 'i'], restype = 'i')(mandel.py_func)

@autojit
def mandel_driver(min_x, max_x, min_y, nb_iterations, colors, image):
    nb_colors = len(colors)
    width = image.shape[0]
    height = image.shape[1]
    pixel_size = (max_x - min_x) / width
    for x in range(width):
        real = min_x + x * pixel_size
        for y in range(height):
            imag = min_y + y * pixel_size
            # For the following to actually compile, mandel_1 must
            # have already been compiled.
            color = mandel(real, imag, nb_iterations)

            # Would prefer the following, just to show off:
            #   image[x, y, :] = colors[color % nb_colors]
            # But that'd require Numba to handle slicing (it doesn't
            # at the time this version was writen), and it wouldn't
            # have the type information about the shape.

            col_index = color % nb_colors # Ohh for wont of CSE...
            image[x, y, 0] = colors[col_index, 0]
            image[x, y, 1] = colors[col_index, 1]
            image[x, y, 2] = colors[col_index, 2]


def make_palette():
    '''Shamefully stolen from
    http://wiki.cython.org/examples/mandelbrot, though we did correct
    their spelling mistakes (*smirk*).'''
    colors = []
    for i in range(0, 25):
        colors.append( (i*10, i*8, 50 + i*8), )
    for i in range(25, 5, -1):
        colors.append( (50 + i*8, 150+i*2,  i*10), )
    for i in range(10, 2, -1):
        colors.append( (0, i*15, 48), )
    return np.array(colors, dtype=np.uint8)

# ______________________________________________________________________

class TestMandelbrot(unittest.TestCase):
    def test_mandel_1_sanity(self):
        self.assertEqual(mandel_1c(0., 0., 20), -1)

    def test_mandel(self):
        vals = np.arange(-1., 1.000001, 0.1)
        for real in vals:
            for imag in vals:
                self.assertEqual(mandel(real, imag, 20),
                                 mandel(real, imag, 20))

    def test_mandel_driver(self):
        palette = make_palette()
        control_image = np.zeros((50, 50, 3), dtype = np.uint8)
        mandel_driver.py_func(-1., 1., -1., len(palette), palette, control_image)
        test_image = np.zeros_like(control_image)
        self.assertTrue((control_image - test_image == control_image).all())
        mandel_driver(-1., 1., -1., len(palette), palette, test_image)
        image_diff = control_image - test_image
        self.assertTrue((image_diff == 0).all())

# ______________________________________________________________________

if __name__ == "__main__":
    unittest.main()

# ______________________________________________________________________
# End of test_mandelbrot.py
