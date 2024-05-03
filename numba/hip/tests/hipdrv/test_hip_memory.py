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

import ctypes

import numpy as np

from numba.hip.hipdrv import driver, devices

drvapi = None  # HIP: driver.USE_NV_BINDING is always True
from numba.hip.testing import unittest, ContextResettingTestCase
from numba.hip.testing import skip_on_hipsim as skip_on_cudasim


@skip_on_cudasim("CUDA Memory API unsupported in the simulator")
class TestCudaMemory(ContextResettingTestCase):
    def setUp(self):
        super().setUp()
        self.context = devices.get_context()

    def tearDown(self):
        del self.context
        super(TestCudaMemory, self).tearDown()

    def _template(self, obj):
        self.assertTrue(driver.is_device_memory(obj))
        driver.require_device_memory(obj)
        if driver.USE_NV_BINDING:
            expected_class = driver.CUdeviceptr
        else:
            expected_class = drvapi.cu_device_ptr
        self.assertTrue(isinstance(obj.device_ctypes_pointer, expected_class))

    def test_device_memory(self):
        devmem = self.context.memalloc(1024)
        self._template(devmem)

    def test_device_view(self):
        devmem = self.context.memalloc(1024)
        self._template(devmem.view(10))

    def test_host_alloc(self):
        devmem = self.context.memhostalloc(1024, mapped=True)
        self._template(devmem)

    def test_pinned_memory(self):
        ary = np.arange(10)
        devmem = self.context.mempin(
            ary, ary.ctypes.data, ary.size * ary.dtype.itemsize, mapped=True
        )
        self._template(devmem)

    def test_managed_memory(self):
        devmem = self.context.memallocmanaged(1024)
        self._template(devmem)

    def test_derived_pointer(self):
        # Use MemoryPointer.view to create derived pointer

        def handle_val(mem):
            if driver.USE_NV_BINDING:
                return int(mem.handle)
            else:
                return mem.handle.value

        def check(m, offset):
            # create view
            v1 = m.view(offset)
            self.assertEqual(handle_val(v1.owner), handle_val(m))
            self.assertEqual(m.refct, 2)
            self.assertEqual(handle_val(v1) - offset, handle_val(v1.owner))
            # create a view
            v2 = v1.view(offset)
            self.assertEqual(handle_val(v2.owner), handle_val(m))
            self.assertEqual(handle_val(v2.owner), handle_val(m))
            self.assertEqual(handle_val(v2) - offset * 2, handle_val(v2.owner))
            self.assertEqual(m.refct, 3)
            del v2
            self.assertEqual(m.refct, 2)
            del v1
            self.assertEqual(m.refct, 1)

        m = self.context.memalloc(1024)
        check(m=m, offset=0)
        check(m=m, offset=1)

    def test_user_extension(self):
        # User can use MemoryPointer to wrap externally defined pointers.
        # This test checks if the finalizer is invokded at correct time
        fake_ptr = ctypes.c_void_p(0xDEADBEEF)
        dtor_invoked = [0]

        def dtor():
            dtor_invoked[0] += 1

        # Ensure finalizer is called when pointer is deleted
        ptr = driver.MemoryPointer(
            context=self.context, pointer=fake_ptr, size=40, finalizer=dtor
        )
        self.assertEqual(dtor_invoked[0], 0)
        del ptr
        self.assertEqual(dtor_invoked[0], 1)

        # Ensure removing derived pointer doesn't call finalizer
        ptr = driver.MemoryPointer(
            context=self.context, pointer=fake_ptr, size=40, finalizer=dtor
        )
        owned = ptr.own()
        del owned
        self.assertEqual(dtor_invoked[0], 1)
        del ptr
        self.assertEqual(dtor_invoked[0], 2)


class TestCudaMemoryFunctions(ContextResettingTestCase):
    def setUp(self):
        super().setUp()
        self.context = devices.get_context()

    def tearDown(self):
        del self.context
        super(TestCudaMemoryFunctions, self).tearDown()

    def test_memcpy(self):
        hstary = np.arange(100, dtype=np.uint32)
        hstary2 = np.arange(100, dtype=np.uint32)
        sz = hstary.size * hstary.dtype.itemsize
        devary = self.context.memalloc(sz)

        driver.host_to_device(devary, hstary, sz)
        driver.device_to_host(hstary2, devary, sz)

        self.assertTrue(np.all(hstary == hstary2))

    def test_memset(self):
        dtype = np.dtype("uint32")
        n = 10
        sz = dtype.itemsize * 10
        devary = self.context.memalloc(sz)
        driver.device_memset(devary, 0xAB, sz)

        hstary = np.empty(n, dtype=dtype)
        driver.device_to_host(hstary, devary, sz)

        hstary2 = np.array([0xABABABAB] * n, dtype=np.dtype("uint32"))
        self.assertTrue(np.all(hstary == hstary2))

    def test_d2d(self):
        hst = np.arange(100, dtype=np.uint32)
        hst2 = np.empty_like(hst)
        sz = hst.size * hst.dtype.itemsize
        dev1 = self.context.memalloc(sz)
        dev2 = self.context.memalloc(sz)
        driver.host_to_device(dev1, hst, sz)
        driver.device_to_device(dev2, dev1, sz)
        driver.device_to_host(hst2, dev2, sz)
        self.assertTrue(np.all(hst == hst2))


@skip_on_cudasim("CUDA Memory API unsupported in the simulator")
class TestMVExtent(ContextResettingTestCase):
    def test_c_contiguous_array(self):
        ary = np.arange(100)
        arysz = ary.dtype.itemsize * ary.size
        s, e = driver.host_memory_extents(ary)
        self.assertTrue(ary.ctypes.data == s)
        self.assertTrue(arysz == driver.host_memory_size(ary))

    def test_f_contiguous_array(self):
        ary = np.asfortranarray(np.arange(100).reshape(2, 50))
        arysz = ary.dtype.itemsize * np.prod(ary.shape)
        s, e = driver.host_memory_extents(ary)
        self.assertTrue(ary.ctypes.data == s)
        self.assertTrue(arysz == driver.host_memory_size(ary))

    def test_single_element_array(self):
        ary = np.asarray(np.uint32(1234))
        arysz = ary.dtype.itemsize
        s, e = driver.host_memory_extents(ary)
        self.assertTrue(ary.ctypes.data == s)
        self.assertTrue(arysz == driver.host_memory_size(ary))

    def test_ctypes_struct(self):
        class mystruct(ctypes.Structure):
            _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

        data = mystruct(x=123, y=432)
        sz = driver.host_memory_size(data)
        self.assertTrue(ctypes.sizeof(data) == sz)

    def test_ctypes_double(self):
        data = ctypes.c_double(1.234)
        sz = driver.host_memory_size(data)
        self.assertTrue(ctypes.sizeof(data) == sz)


if __name__ == "__main__":
    unittest.main()
