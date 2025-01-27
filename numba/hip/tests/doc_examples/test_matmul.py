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

from numba import hip
hip.pose_as_cuda()

# unchanged original unit Numba CUDA test code below:

"""
Matrix multiplication example via `cuda.jit`.

Reference: https://stackoverflow.com/a/64198479/13697228 by @RobertCrovella

Contents in this file are referenced from the sphinx-generated docs.
"magictoken" is used for markers as beginning and ending of example text.
"""

import unittest
from numba.cuda.testing import CUDATestCase, skip_on_cudasim
from numba.tests.support import captured_stdout


@skip_on_cudasim("cudasim doesn't support cuda import at non-top-level")
class TestMatMul(CUDATestCase):
    """
    Text matrix multiplication using simple, shared memory/square, and shared
    memory/nonsquare cases.
    """

    def setUp(self):
        # Prevent output from this test showing up when running the test suite
        self._captured_stdout = captured_stdout()
        self._captured_stdout.__enter__()
        super().setUp()

    def tearDown(self):
        # No exception type, value, or traceback
        self._captured_stdout.__exit__(None, None, None)
        super().tearDown()

    def test_ex_matmul(self):
        """Test of matrix multiplication on various cases."""
        # magictoken.ex_import.begin
        from numba import cuda, float32
        import numpy as np
        import math
        # magictoken.ex_import.end

        # magictoken.ex_matmul.begin
        @cuda.jit
        def matmul(A, B, C):
            """Perform square matrix multiplication of C = A * B."""
            i, j = cuda.grid(2)
            if i < C.shape[0] and j < C.shape[1]:
                tmp = 0.
                for k in range(A.shape[1]):
                    tmp += A[i, k] * B[k, j]
                C[i, j] = tmp
        # magictoken.ex_matmul.end

        # magictoken.ex_run_matmul.begin
        x_h = np.arange(16).reshape([4, 4])
        y_h = np.ones([4, 4])
        z_h = np.zeros([4, 4])

        x_d = cuda.to_device(x_h)
        y_d = cuda.to_device(y_h)
        z_d = cuda.to_device(z_h)

        threadsperblock = (16, 16)
        blockspergrid_x = math.ceil(z_h.shape[0] / threadsperblock[0])
        blockspergrid_y = math.ceil(z_h.shape[1] / threadsperblock[1])
        blockspergrid = (blockspergrid_x, blockspergrid_y)

        matmul[blockspergrid, threadsperblock](x_d, y_d, z_d)
        z_h = z_d.copy_to_host()
        print(z_h)
        print(x_h @ y_h)
        # magictoken.ex_run_matmul.end

        # magictoken.ex_fast_matmul.begin
        # Controls threads per block and shared memory usage.
        # The computation will be done on blocks of TPBxTPB elements.
        # TPB should not be larger than 32 in this example
        TPB = 16

        @cuda.jit
        def fast_matmul(A, B, C):
            """
            Perform matrix multiplication of C = A * B using CUDA shared memory.

            Reference: https://stackoverflow.com/a/64198479/13697228 by @RobertCrovella
            """
            # Define an array in the shared memory
            # The size and type of the arrays must be known at compile time
            sA = cuda.shared.array(shape=(TPB, TPB), dtype=float32)
            sB = cuda.shared.array(shape=(TPB, TPB), dtype=float32)

            x, y = cuda.grid(2)

            tx = cuda.threadIdx.x
            ty = cuda.threadIdx.y
            bpg = cuda.gridDim.x    # blocks per grid

            # Each thread computes one element in the result matrix.
            # The dot product is chunked into dot products of TPB-long vectors.
            tmp = float32(0.)
            for i in range(bpg):
                # Preload data into shared memory
                sA[ty, tx] = 0
                sB[ty, tx] = 0
                if y < A.shape[0] and (tx + i * TPB) < A.shape[1]:
                    sA[ty, tx] = A[y, tx + i * TPB]
                if x < B.shape[1] and (ty + i * TPB) < B.shape[0]:
                    sB[ty, tx] = B[ty + i * TPB, x]

                # Wait until all threads finish preloading
                cuda.syncthreads()

                # Computes partial product on the shared memory
                for j in range(TPB):
                    tmp += sA[ty, j] * sB[j, tx]

                # Wait until all threads finish computing
                cuda.syncthreads()
            if y < C.shape[0] and x < C.shape[1]:
                C[y, x] = tmp
        # magictoken.ex_fast_matmul.end

        # magictoken.ex_run_fast_matmul.begin
        x_h = np.arange(16).reshape([4, 4])
        y_h = np.ones([4, 4])
        z_h = np.zeros([4, 4])

        x_d = cuda.to_device(x_h)
        y_d = cuda.to_device(y_h)
        z_d = cuda.to_device(z_h)

        threadsperblock = (TPB, TPB)
        blockspergrid_x = math.ceil(z_h.shape[0] / threadsperblock[0])
        blockspergrid_y = math.ceil(z_h.shape[1] / threadsperblock[1])
        blockspergrid = (blockspergrid_x, blockspergrid_y)

        fast_matmul[blockspergrid, threadsperblock](x_d, y_d, z_d)
        z_h = z_d.copy_to_host()
        print(z_h)
        print(x_h @ y_h)
        # magictoken.ex_run_fast_matmul.end

        # fast_matmul test(s)
        msg = "fast_matmul incorrect for shared memory, square case."
        self.assertTrue(np.all(z_h == x_h @ y_h), msg=msg)

        # magictoken.ex_run_nonsquare.begin
        x_h = np.arange(115).reshape([5, 23])
        y_h = np.ones([23, 7])
        z_h = np.zeros([5, 7])

        x_d = cuda.to_device(x_h)
        y_d = cuda.to_device(y_h)
        z_d = cuda.to_device(z_h)

        threadsperblock = (TPB, TPB)
        grid_y_max = max(x_h.shape[0], y_h.shape[0])
        grid_x_max = max(x_h.shape[1], y_h.shape[1])
        blockspergrid_x = math.ceil(grid_x_max / threadsperblock[0])
        blockspergrid_y = math.ceil(grid_y_max / threadsperblock[1])
        blockspergrid = (blockspergrid_x, blockspergrid_y)

        fast_matmul[blockspergrid, threadsperblock](x_d, y_d, z_d)
        z_h = z_d.copy_to_host()
        print(z_h)
        print(x_h @ y_h)
        # magictoken.ex_run_nonsquare.end

        # nonsquare fast_matmul test(s)
        msg = "fast_matmul incorrect for shared memory, non-square case."
        self.assertTrue(np.all(z_h == x_h @ y_h), msg=msg)


if __name__ == '__main__':
    unittest.main()
