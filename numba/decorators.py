__all__ = ['function', 'autojit', 'function_bytecode', 'jit_ast', 'jit']

import functools
import logging

import numba
from numba import *
from . import utils, functions, ast_translate as translate
from numba import translate as bytecode_translate
from .minivect import minitypes
from numba.utils import debugout

logger = logging.getLogger(__name__)

# Create a new callable object
#  that creates a fast version of Python code using LLVM
# It maintains the generic function call for situations
#  where it cannot figure out a fast version, and specializes
#  based on the types that are passed in.
#  It maintains a dictionary keyed by python code +
#   argument-types with a tuple of either
#       (bitcode-file-name, function_name)
#  or (llvm mod object and llvm func object)

class CallSite(object):
    # Must support
    # func = CallSite(func)
    # func = CallSite()(func)
    # func = Callsite(*args, **kwds)(func)
    #  args[0] cannot be callable
    def __init__(self, *args, **kwds):
        # True if this instance is now a function
        self._isfunc = False
        self._args = args
        if len(args) > 1 and callable(args[0]):
            self._tocall = args[0]
            self._isfunc = True
            self._args = args[1:]

    def __call__(self, *args, **kwds):
        if self._isfunc:
            return self._tocall(*args, **kwds)
        else:
            if len(args) < 1 or not callable(args[0]):
                raise ValueError, "decorated object must be callable"
            self._tocall = args[0]
            self._isfunc = True
            return self

# A simple fast-vectorize example was removed because it only supports one
#  use-case --- slower NumPy vectorize is included here instead.
#  The required code is still in _ext.c which is not compiled by default
#   and here is the decorator:
#def vectorize(func):
#    global __tr_map__
#    try:
#        if func not in __tr_map__:
#            t = Translate(func)
#            t.translate()
#            __tr_map__[func] = t
#        else:
#            t = __tr_map__[func]
#        return t.make_ufunc()
#    except Exception as msg:
#        print "Warning: Could not create fast version...", msg
#        import traceback
#        traceback.print_exc()
#        import numpy
#        return numpy.vectorize(func)

from numpy import vectorize

# The __tr_map__ global maps from Python functions to a Translate
# object.  This added reference prevents the translator and its
# generated LLVM code from being garbage collected when we leave the
# scope of a decorator.

# See: https://github.com/ContinuumIO/numba/issues/5

__tr_map__ = {}

context = utils.get_minivect_context()
context.llvm_context = translate.LLVMContextManager()
function_cache = context.function_cache = functions.FunctionCache(context)

def function(f):
    """
    Defines a numba function, that, when called, specializes on the input
    types. Uses the AST translator backend. For the bytecode translator,
    use @autojit.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        arguments = args + tuple(kwargs[k] for k in sorted(kwargs))
        types = tuple(context.typemapper.from_python(value)
                          for value in arguments)
        ctypes_func = jit_ast(arg_types=types)(f)
        return ctypes_func(*args, **kwargs)

    wrapper._is_numba_func = True
    wrapper._numba_func = f
    return wrapper

# Bit of an inconsistency with jit_ast() vs jit(), but we already used
# @function()...
_func_cache = {}
def function_bytecode(f):
    """
    Defines a numba function, that, when called, specializes on the input
    types. Uses the bytecode translator backend. For the AST backend use
    @function.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # Infer argument types
        arguments = args + tuple(kwargs[k] for k in sorted(kwargs))
        types = tuple(context.typemapper.from_python(value)
                          for value in arguments)
        if types in _func_cache:
            ctypes_func = _func_cache[types]
        else:
            # Infer the return type
            func_signature, symtab, ast = functions._infer_types(
                                        context, f, arg_types=types)

            decorator = jit(ret_type=func_signature.return_type, arg_types=types)
            ctypes_func = decorator(f)
            _func_cache[types] = ctypes_func

        return ctypes_func(*args, **kwargs)

    wrapper._is_numba_func = True
    wrapper._numba_func = f
    return wrapper

autojit = function_bytecode

def jit_ast(ret_type=None, arg_types=None):
    """
    Use the AST translator to translate the function.
    """
    assert arg_types is not None

    def _jit(func):
        func._is_numba_func = True
        result = function_cache.compile_function(func, arg_types)
        _, _, ctypes_func = result
        return ctypes_func

    return _jit

def jit(ret_type=double, arg_types=[double], backend='bytecode', **kws):
    """
    Compile a function given the input and return types. If backend='bytecode'
    the bytecode translator is used, if backend='ast' the AST translator is
    used.
    """
    def _jit(func):
        global __tr_map__
        llvm = kws.pop('llvm', True)
        if func in __tr_map__:
            logger.warning("Warning: Previously compiled version of %r may be "
                           "garbage collected!" % (func,))

        use_ast = False
        if backend == 'ast':
            use_ast = True
            for arg_type in list(arg_types) + [ret_type]:
                if not isinstance(arg_type, minitypes.Type):
                    use_ast = False
                    debugout("String type specified, using bytecode translator...")
                    break

        if use_ast:
            return jit_ast(arg_types=arg_types)(func)
        else:
            t = bytecode_translate.Translate(func, ret_type=ret_type,
                                             arg_types=arg_types, **kws)
            t.translate()
            __tr_map__[func] = t
            return t.get_ctypes_func(llvm)

    return _jit
