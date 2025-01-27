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

from itertools import product

import numpy as np

from numba import hip as cuda
from numba.hip.testing import (
    unittest,
    HIPTestCase as CUDATestCase,
)  # , skip_on_cudasim TODO(HIP/AMD) enable simulator
from unittest.mock import patch


class CudaArrayIndexing(CUDATestCase):
    def test_index_1d(self):
        arr = np.arange(10)
        darr = cuda.to_device(arr)
        (x,) = arr.shape
        for i in range(-x, x):
            self.assertEqual(arr[i], darr[i])
        with self.assertRaises(IndexError):
            darr[-x - 1]
        with self.assertRaises(IndexError):
            darr[x]

    def test_index_2d(self):
        arr = np.arange(3 * 4).reshape(3, 4)
        darr = cuda.to_device(arr)
        x, y = arr.shape
        for i in range(-x, x):
            for j in range(-y, y):
                self.assertEqual(arr[i, j], darr[i, j])
        with self.assertRaises(IndexError):
            darr[-x - 1, 0]
        with self.assertRaises(IndexError):
            darr[x, 0]
        with self.assertRaises(IndexError):
            darr[0, -y - 1]
        with self.assertRaises(IndexError):
            darr[0, y]

    def test_index_3d(self):
        arr = np.arange(3 * 4 * 5).reshape(3, 4, 5)
        darr = cuda.to_device(arr)
        x, y, z = arr.shape
        for i in range(-x, x):
            for j in range(-y, y):
                for k in range(-z, z):
                    self.assertEqual(arr[i, j, k], darr[i, j, k])
        with self.assertRaises(IndexError):
            darr[-x - 1, 0, 0]
        with self.assertRaises(IndexError):
            darr[x, 0, 0]
        with self.assertRaises(IndexError):
            darr[0, -y - 1, 0]
        with self.assertRaises(IndexError):
            darr[0, y, 0]
        with self.assertRaises(IndexError):
            darr[0, 0, -z - 1]
        with self.assertRaises(IndexError):
            darr[0, 0, z]


class CudaArrayStridedSlice(CUDATestCase):

    def test_strided_index_1d(self):
        arr = np.arange(10)
        darr = cuda.to_device(arr)
        for i in range(arr.size):
            np.testing.assert_equal(arr[i::2], darr[i::2].copy_to_host())

    def test_strided_index_2d(self):
        arr = np.arange(6 * 7).reshape(6, 7)
        darr = cuda.to_device(arr)

        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                np.testing.assert_equal(
                    arr[i::2, j::2], darr[i::2, j::2].copy_to_host()
                )

    def test_strided_index_3d(self):
        arr = np.arange(6 * 7 * 8).reshape(6, 7, 8)
        darr = cuda.to_device(arr)

        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                for k in range(arr.shape[2]):
                    np.testing.assert_equal(
                        arr[i::2, j::2, k::2], darr[i::2, j::2, k::2].copy_to_host()
                    )


class CudaArraySlicing(CUDATestCase):
    def test_prefix_1d(self):
        arr = np.arange(5)
        darr = cuda.to_device(arr)
        for i in range(arr.size):
            expect = arr[i:]
            got = darr[i:].copy_to_host()
            self.assertTrue(np.all(expect == got))

    def test_prefix_2d(self):
        arr = np.arange(3**2).reshape(3, 3)
        darr = cuda.to_device(arr)
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                expect = arr[i:, j:]
                sliced = darr[i:, j:]
                self.assertEqual(expect.shape, sliced.shape)
                self.assertEqual(expect.strides, sliced.strides)
                got = sliced.copy_to_host()
                self.assertTrue(np.all(expect == got))

    def test_select_3d_first_two_dim(self):
        arr = np.arange(3 * 4 * 5).reshape(3, 4, 5)
        darr = cuda.to_device(arr)
        # Select first dimension
        for i in range(arr.shape[0]):
            expect = arr[i]
            sliced = darr[i]
            self.assertEqual(expect.shape, sliced.shape)
            self.assertEqual(expect.strides, sliced.strides)
            got = sliced.copy_to_host()
            self.assertTrue(np.all(expect == got))
        # Select second dimension
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                expect = arr[i, j]
                sliced = darr[i, j]
                self.assertEqual(expect.shape, sliced.shape)
                self.assertEqual(expect.strides, sliced.strides)
                got = sliced.copy_to_host()
                self.assertTrue(np.all(expect == got))

    def test_select_f(self):
        """
        TODO (HIP):
            Non-contiguous memory copies are failing in this test.
            For some reason, strides are not taken into account by the
            slicing when creating a new memory buffer for carrying the sliced out elements.
            This would be fine if the strides were taken into account
            when doing host<->device copies but this seems also not to be the case.
        """
        # 1. 'a' is first created as 1-D array of size 5*6*7, with
        # the elements 0 ... 5*6*7-1.
        # 2. 'a' is then reshaped to have shape (5,6,7),
        # where the fastest running index is associated with the dimension
        # with size 7 in case of order 'C' and that of size 5 in case of order 'F'.
        # Independent of the order ('F'/'C'), the resulting shape is the same.
        a = np.arange(5 * 6 * 7).reshape(5, 6, 7, order="F")
        # print(f"a size={a.size*a.itemsize}")
        # print(a)
        # print(a[0,0,:])
        da = cuda.to_device(a)

        ## TODO(HIP/AMD) non-contiguous memcopy fails
        # for i in range(a.shape[0]):
        #     for j in range(a.shape[1]):
        #         suba = a[i, j, :]
        #         self.assertTrue(da[i, j, :].size == 7)
        #         print(f"a[{i},{j},:] size={suba.size*suba.itemsize}")
        #         self.assertTrue(np.array_equal(da[i, j, :].copy_to_host(),
        #                                        a[i, j, :]))
        ## TODO(HIP/AMD) non-contiguous memcopy fails
        # for j in range(a.shape[2]):
        #     self.assertTrue(np.array_equal(da[i, :, j].copy_to_host(),
        #                                    a[i, :, j]))
        for i in range(a.shape[1]):
            for j in range(a.shape[2]):
                self.assertTrue(np.array_equal(da[:, i, j].copy_to_host(), a[:, i, j]))

    def test_select_c(self):
        """
        TODO (HIP):
            Non-contiguous memory copies are failing in this test.
            For some reason, strides are not taken into account by the
            slicing when creating a new memory buffer for carrying the sliced out elements.
            This would be fine if the strides were taken into account
            when doing host<->device copies but this seems also not to be the case.
        """
        a = np.arange(5 * 6 * 7).reshape(5, 6, 7, order="C")
        da = cuda.to_device(a)

        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                # z-y slice, x stride is 1 (8 B, double)
                # print(f"\nNEW {i},{j}\n")
                self.assertTrue(np.array_equal(da[i, j, :].copy_to_host(), a[i, j, :]))
            ## TODO(HIP/AMD) non-contiguous memcopy fails
            # for j in range(a.shape[2]):
            #     # z-x slice, y stride is 7 (56 B, 7x double), size of a z-x-slice is 6 (48 B).
            #     # print(f"\nNEW {i},{j}\n")
            #     self.assertTrue(np.array_equal(da[i, :, j].copy_to_host(),
            #                                    a[i, :, j]))
        ## TODO(HIP/AMD) non-contiguous memcopy fails
        # for i in range(a.shape[1]):
        #     for j in range(a.shape[2]):
        #         self.assertTrue(np.array_equal(da[:, i, j].copy_to_host(),
        #                                        a[:, i, j]))

    def test_prefix_select(self):
        arr = np.arange(5 * 7).reshape(5, 7, order="F")

        darr = cuda.to_device(arr)
        self.assertTrue(np.all(darr[:1, 1].copy_to_host() == arr[:1, 1]))

    def test_negative_slicing_1d(self):
        arr = np.arange(10)
        darr = cuda.to_device(arr)
        for i, j in product(range(-10, 10), repeat=2):
            np.testing.assert_array_equal(arr[i:j], darr[i:j].copy_to_host())

    def test_negative_slicing_2d(self):
        arr = np.arange(12).reshape(3, 4)
        darr = cuda.to_device(arr)
        for x, y, w, s in product(range(-4, 4), repeat=4):
            np.testing.assert_array_equal(arr[x:y, w:s], darr[x:y, w:s].copy_to_host())

    def test_empty_slice_1d(self):
        arr = np.arange(5)
        darr = cuda.to_device(arr)
        for i in range(darr.shape[0]):
            np.testing.assert_array_equal(darr[i:i].copy_to_host(), arr[i:i])
        # empty slice of empty slice
        self.assertFalse(darr[:0][:0].copy_to_host())
        # out-of-bound slice just produces empty slices
        np.testing.assert_array_equal(darr[:0][:1].copy_to_host(), arr[:0][:1])
        np.testing.assert_array_equal(darr[:0][-1:].copy_to_host(), arr[:0][-1:])

    def test_empty_slice_2d(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        np.testing.assert_array_equal(darr[:0].copy_to_host(), arr[:0])
        np.testing.assert_array_equal(darr[3, :0].copy_to_host(), arr[3, :0])
        # empty slice of empty slice
        self.assertFalse(darr[:0][:0].copy_to_host())
        # out-of-bound slice just produces empty slices
        np.testing.assert_array_equal(darr[:0][:1].copy_to_host(), arr[:0][:1])
        np.testing.assert_array_equal(darr[:0][-1:].copy_to_host(), arr[:0][-1:])


class CudaArraySetting(CUDATestCase):
    """
    Most of the slicing logic is tested in the cases above, so these
    tests focus on the setting logic.
    """

    def test_scalar(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        arr[2, 2] = 500
        darr[2, 2] = 500
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_rank(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        arr[2] = 500
        darr[2] = 500
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    # TODO(HIP/AMD) segmentation fault
    @unittest.skip("TODO(HIP/AMD) segmentation fault")
    def test_broadcast(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        arr[:, 2] = 500
        darr[:, 2] = 500
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_array_assign_column(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        _400 = np.full(shape=7, fill_value=400)
        arr[2] = _400
        darr[2] = _400
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    # TODO(HIP/AMD) segmentation fault
    @unittest.skip("TODO(HIP/AMD) segmentation fault")
    def test_array_assign_row(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        _400 = np.full(shape=5, fill_value=400)
        arr[:, 2] = _400
        darr[:, 2] = _400
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_array_assign_subarray(self):
        arr = np.arange(5 * 6 * 7).reshape(5, 6, 7)
        darr = cuda.to_device(arr)
        _400 = np.full(shape=(6, 7), fill_value=400)
        arr[2] = _400
        darr[2] = _400
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    # TODO(HIP/AMD) segmentation fault
    @unittest.skip("TODO(HIP/AMD) segmentation fault")
    def test_array_assign_deep_subarray(self):
        arr = np.arange(5 * 6 * 7 * 8).reshape(5, 6, 7, 8)
        darr = cuda.to_device(arr)
        _400 = np.full(shape=(5, 6, 8), fill_value=400)
        arr[:, :, 2] = _400
        darr[:, :, 2] = _400
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_array_assign_all(self):
        arr = np.arange(5 * 7).reshape(5, 7)
        darr = cuda.to_device(arr)
        _400 = np.full(shape=(5, 7), fill_value=400)
        arr[:] = _400
        darr[:] = _400
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_strides(self):
        arr = np.ones(20)
        darr = cuda.to_device(arr)
        arr[::2] = 500
        darr[::2] = 500
        np.testing.assert_array_equal(darr.copy_to_host(), arr)

    def test_incompatible_highdim(self):
        darr = cuda.to_device(np.arange(5 * 7))

        with self.assertRaises(ValueError) as e:
            darr[:] = np.ones(shape=(1, 2, 3))

        self.assertIn(
            member=str(e.exception),
            container=[
                "Can't assign 3-D array to 1-D self",  # device
                "could not broadcast input array from shape (2,3) "
                "into shape (35,)",  # simulator, NP >= 1.20
            ],
        )

    def test_incompatible_shape(self):
        darr = cuda.to_device(np.arange(5))

        with self.assertRaises(ValueError) as e:
            darr[:] = [1, 3]

        self.assertIn(
            member=str(e.exception),
            container=[
                "Can't copy sequence with size 2 to array axis 0 with "
                "dimension 5",  # device
                "could not broadcast input array from shape (2,) into "
                "shape (5,)",  # simulator, NP >= 1.20
            ],
        )

    # @skip_on_cudasim('cudasim does not use streams and operates synchronously')
    def test_sync(self):
        # There should be a synchronization when no stream is supplied
        darr = cuda.to_device(np.arange(5))

        with patch.object(
            cuda.cudadrv.driver.Stream, "synchronize", return_value=None
        ) as mock_sync:
            darr[0] = 10

        mock_sync.assert_called_once()

    # @skip_on_cudasim('cudasim does not use streams and operates synchronously')
    def test_no_sync_default_stream(self):
        # There should not be a synchronization when the array has a default
        # stream, whether it is the default stream, the legacy default stream,
        # the per-thread default stream, or another stream.
        streams = (
            cuda.stream(),
            cuda.default_stream(),
            cuda.legacy_default_stream(),
            cuda.per_thread_default_stream(),
        )

        for stream in streams:
            darr = cuda.to_device(np.arange(5), stream=stream)

            with patch.object(
                cuda.cudadrv.driver.Stream, "synchronize", return_value=None
            ) as mock_sync:
                darr[0] = 10

            mock_sync.assert_not_called()

    # @skip_on_cudasim('cudasim does not use streams and operates synchronously')
    def test_no_sync_supplied_stream(self):
        # There should not be a synchronization when a stream is supplied for
        # the setitem call, whether it is the default stream, the legacy default
        # stream, the per-thread default stream, or another stream.
        streams = (
            cuda.stream(),
            cuda.default_stream(),
            cuda.legacy_default_stream(),
            cuda.per_thread_default_stream(),
        )

        for stream in streams:
            darr = cuda.to_device(np.arange(5))

            with patch.object(
                cuda.cudadrv.driver.Stream, "synchronize", return_value=None
            ) as mock_sync:
                darr.setitem(0, 10, stream=stream)

            mock_sync.assert_not_called()

    @unittest.skip("Requires PR #6367")
    def test_issue_6505(self):
        # On Windows, the writes to ary_v would not be visible prior to the
        # assertion, due to the assignment being done with a kernel launch that
        # returns asynchronously - there should now be a sync after the kernel
        # launch to ensure that the writes are always visible.
        ary = cuda.mapped_array(2, dtype=np.int32)
        ary[:] = 0

        ary_v = ary.view("u1")
        ary_v[1] = 1
        ary_v[5] = 1
        self.assertEqual(sum(ary), 512)


if __name__ == "__main__":
    unittest.main()
