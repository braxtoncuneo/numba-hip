# Copyright (c) 2012, Anaconda, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# MIT License
#
# Modifications Copyright (C) 2023-2024 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# CUDA built-in Vector Types
# https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#built-in-vector-types

from typing import List, Tuple, Dict

from numba import types
from numba.core import cgutils
from numba.core.extending import make_attribute_wrapper, models, register_model
from numba.core.typing.templates import ConcreteTemplate
from numba.core.typing.templates import signature
from numba.hip.typing_lowering.hip import hipstubs as stubs
from numba.hip.errors import HipLoweringError

from numba.hip.typing_lowering.registries import (
    typing_registry,
    impl_registry
)

register = typing_registry.register
register_attr = typing_registry.register_attr
register_global = typing_registry.register_global
lower = impl_registry.lower


class VectorType(types.Type):
    def __init__(self, name, base_type, attr_names, user_facing_object):
        self._base_type = base_type
        self._attr_names = attr_names
        self._user_facing_object = user_facing_object
        super().__init__(name=name)

    @property
    def base_type(self):
        return self._base_type

    @property
    def attr_names(self):
        return self._attr_names

    @property
    def num_elements(self):
        return len(self._attr_names)

    @property
    def user_facing_object(self):
        return self._user_facing_object


def make_vector_type(
    name: str,
    base_type: types.Type,
    attr_names: Tuple[str, ...],
    user_facing_object
) -> types.Type:
    """Create a vector type.

    Parameters
    ----------
    name: str
        The name of the type.
    base_type: numba.types.Type
        The primitive type for each element in the vector.
    attr_names: tuple of str
        Name for each attribute.
    user_facing_object: object
        The handle to be used in cuda kernel.
    """

    class _VectorType(VectorType):
        """Internal instantiation of VectorType."""

        pass

    class VectorTypeModel(models.StructModel):
        def __init__(self, dmm, fe_type):
            members = [(attr_name, base_type) for attr_name in attr_names]
            super().__init__(dmm, fe_type, members)

    vector_type = _VectorType(name, base_type, attr_names, user_facing_object)
    register_model(_VectorType)(VectorTypeModel)
    for attr_name in attr_names:
        make_attribute_wrapper(_VectorType, attr_name, attr_name)

    return vector_type


def enable_vector_type_ctor(
    vector_type: VectorType, overloads: List[List[types.Type]]
):
    """Create typing and lowering for vector type constructor.

    Parameters
    ----------
    vector_type: VectorType
        The type whose constructor to type and lower.
    overloads: List of argument types
        A list containing different overloads of the constructor. Each base type
        in the argument list should either be primitive type or VectorType.
    """
    ctor = vector_type.user_facing_object

    @register
    class CtorTemplate(ConcreteTemplate):
        key = ctor
        cases = [signature(vector_type, *arglist) for arglist in overloads]

    register_global(ctor, types.Function(CtorTemplate))

    # Lowering

    def make_lowering(fml_arg_list):
        """Meta function to create a lowering for the constructor. Flattens
        the arguments by converting vector_type into load instructions for each
        of its attributes. Such as float2 -> float2.x, float2.y.
        """

        def lowering(context, builder, sig, actual_args):
            # A list of elements to assign from
            source_list = []
            # Convert the list of argument types to a list of load IRs.
            for argidx, fml_arg in enumerate(fml_arg_list):
                if isinstance(fml_arg, VectorType):
                    pxy = cgutils.create_struct_proxy(fml_arg)(
                        context, builder, actual_args[argidx]
                    )
                    source_list += [
                        getattr(pxy, attr) for attr in fml_arg.attr_names
                    ]
                else:
                    # assumed primitive type
                    source_list.append(actual_args[argidx])

            if len(source_list) != vector_type.num_elements:
                raise HipLoweringError(
                    f"Unmatched number of source elements ({len(source_list)}) "
                    "and target elements ({vector_type.num_elements})."
                )

            out = cgutils.create_struct_proxy(vector_type)(context, builder)

            for attr_name, source in zip(vector_type.attr_names, source_list):
                setattr(out, attr_name, source)
            return out._getvalue()

        return lowering

    for arglist in overloads:
        lowering = make_lowering(arglist)
        lower(ctor, *arglist)(lowering)


vector_types : Dict[str, VectorType] = {}


def build_constructor_overloads(base_type, vty_name, num_elements, arglists, l):
    """
    For a given vector type, build a list of overloads for its constructor.
    """

    # TODO: speed up with memoization
    if num_elements == 0:
        arglists.append(l[:])

    for i in range(1, num_elements + 1):
        if i == 1:
            # For 1-element component, it can construct with either a
            # primitive type or other 1-element component.
            l.append(base_type)
            build_constructor_overloads(
                base_type, vty_name, num_elements - i, arglists, l
            )
            l.pop(-1)

            l.append(vector_types[f"{vty_name[:-1]}1"])
            build_constructor_overloads(
                base_type, vty_name, num_elements - i, arglists, l
            )
            l.pop(-1)
        else:
            l.append(vector_types[f"{vty_name[:-1]}{i}"])
            build_constructor_overloads(
                base_type, vty_name, num_elements - i, arglists, l
            )
            l.pop(-1)


def _initialize():
    """
    Construct the vector types, populate `vector_types` dictionary, and
    enable the constructors.
    """
    vector_type_attribute_names = ("x", "y", "z", "w")
    for stub in stubs._vector_type_stubs:
        type_name = stub.__name__
        base_type = getattr(types, type_name[:-2])
        num_elements = int(type_name[-1])
        attributes = vector_type_attribute_names[:num_elements]
        vector_type = make_vector_type(type_name, base_type, attributes, stub)
        vector_types[type_name] = vector_type

    for vty in vector_types.values():
        arglists, l = [], []
        build_constructor_overloads(
            vty.base_type, vty.name, vty.num_elements, arglists, l
        )
        enable_vector_type_ctor(vty, arglists)


_initialize()
