"Filter definitions, with pre-processing, post-processing and compilation methods."

import numpy as np
import torch
from torch import nn
from common import AVAILABLE_FILTERS, INPUT_SHAPE

from concrete.fhe.compilation.compiler import Compiler
from concrete.ml.common.utils import generate_proxy_function
from concrete.ml.torch.numpy_module import NumpyModule


class TorchIdentity(nn.Module):
    """Torch identity model."""

    def forward(self, x):
        """Identity forward pass.

        Args:
            x (torch.Tensor): The input image.

        Returns:
            x (torch.Tensor): The input image.
        """
        return x


class TorchInverted(nn.Module):
    """Torch inverted model."""

    def forward(self, x):
        """Forward pass for inverting an image's colors.

        Args:
            x (torch.Tensor): The input image.

        Returns:
            torch.Tensor: The (color) inverted image.
        """
        return 255 - x


class TorchRotate(nn.Module):
    """Torch rotated model."""

    def forward(self, x):
        """Forward pass for rotating an image.

        Args:
            x (torch.Tensor): The input image.

        Returns:
            torch.Tensor: The rotated image.
        """
        return x.transpose(0, 1)


class TorchConv(nn.Module):
    """Torch model with a single convolution operator."""

    def __init__(self, kernel, n_in_channels=3, n_out_channels=3, groups=1, threshold=None):
        """Initialize the filter.

        Args:
            kernel (np.ndarray): The convolution kernel to consider.
        """
        super().__init__()
        self.kernel = torch.tensor(kernel, dtype=torch.int64)
        self.n_out_channels = n_out_channels
        self.n_in_channels = n_in_channels
        self.groups = groups
        self.threshold = threshold

    def forward(self, x):
        """Forward pass with a single convolution using a 1D or 2D kernel.

        Args:
            x (torch.Tensor): The input image.

        Returns:
            torch.Tensor: The filtered image.
        """
        # Define the convolution parameters
        stride = 1
        kernel_shape = self.kernel.shape

        # Ensure the kernel has a proper shape
        # If the kernel has a 1D shape, a (1, 1) kernel is used for each in_channels
        if len(kernel_shape) == 1:
            self.kernel = self.kernel.repeat(self.n_out_channels)
            kernel = self.kernel.reshape(
                self.n_out_channels,
                self.n_in_channels // self.groups,
                1,
                1,
            )

        # Else, if the kernel has a 2D shape, a single (Kw, Kh) kernel is used on all in_channels
        elif len(kernel_shape) == 2:
            kernel = self.kernel.expand(
                self.n_out_channels,
                self.n_in_channels // self.groups,
                kernel_shape[0],
                kernel_shape[1],
            )


        else:
            raise ValueError(
                "Wrong kernel shape, only 1D or 2D kernels are accepted. Got kernel of shape "
                f"{kernel_shape}"
            )

        # Reshape the image. This is done because Torch convolutions and Numpy arrays (for PIL 
        # display) don't follow the same shape conventions. More precisely, x is of shape 
        # (Width, Height, Channels) while the conv2d operator requires an input of shape 
        # (Batch, Channels, Height, Width)
        x = x.transpose(2, 0).unsqueeze(axis=0)

        # Apply the convolution
        x = nn.functional.conv2d(x, kernel, stride=stride, groups=self.groups)

        # Reshape the output back to the original shape (Width, Height, Channels)
        x = x.transpose(1, 3).reshape((x.shape[2], x.shape[3], self.n_out_channels))

        # Subtract a given threshold if given
        if self.threshold is not None:
            x -= self.threshold

        return x


class Filter:
    """Filter class used in the app."""

    def __init__(self, filter_name):
        """Initializing the filter class using a given filter.

        Most filters can be found at https://en.wikipedia.org/wiki/Kernel_(image_processing).

        Args:
            filter_name (str): The filter to consider.
        """

        assert filter_name in AVAILABLE_FILTERS, (
            f"Unsupported image filter or transformation. Expected one of {*AVAILABLE_FILTERS,}, "
            f"but got {filter_name}",
        )

        # Define attributes associated to the filter 
        self.filter_name = filter_name
        self.onnx_model = None
        self.fhe_circuit = None
        self.divide = None

        # Instantiate the torch module associated to the given filter name 
        if filter_name == "identity":
            self.torch_model = TorchIdentity()

        elif filter_name == "inverted":
            self.torch_model = TorchInverted()

        elif filter_name == "rotate":
            self.torch_model = TorchRotate()

        elif filter_name == "black and white":
            # Define the grayscale weights (RGB order)
            # These weights were used in PAL and NTSC video systems and can be found at
            # https://en.wikipedia.org/wiki/Grayscale
            # There are initially supposed to be float weights (0.299, 0.587, 0.114), with
            # 0.299 + 0.587 + 0.114 = 1
            # However, since FHE computations require weights to be integers, we first multiply
            # these by a factor of 1000. The output image's values are then divided by 1000 in
            # post-processing in order to retrieve the correct result
            kernel = [299, 587, 114]

            self.torch_model = TorchConv(kernel)

            # Define the value used when for dividing the output values in post-processing
            self.divide = 1000


        elif filter_name == "blur":
            kernel = np.ones((3, 3))

            self.torch_model = TorchConv(kernel, groups=3)

            # Define the value used when for dividing the output values in post-processing
            self.divide = 9

        elif filter_name == "sharpen":
            kernel = [
                [0, -1, 0],
                [-1, 5, -1],
                [0, -1, 0],
            ]

            self.torch_model = TorchConv(kernel, groups=3)

        elif filter_name == "ridge detection":
            kernel = [
                [-1, -1, -1],
                [-1, 9, -1],
                [-1, -1, -1],
            ]

            # Additionally to the convolution operator, the filter will subtract a given threshold
            # value to the result in order to better display the ridges
            self.torch_model = TorchConv(kernel, threshold=900)


    def compile(self):
        """Compile the filter on a representative inputset."""
        # Generate a random representative set of images used for compilation, following shape 
        # PIL's shape RGB format for Numpy arrays (image_width, image_height, 3)
        # Additionally, this version's compiler only handles tuples of 1-batch array as inputset, 
        # meaning we need to define the inputset as a Tuple[np.ndarray[shape=(H, W, 3)]]  
        np.random.seed(42)
        inputset = tuple(
            np.random.randint(0, 256, size=(INPUT_SHAPE + (3, )), dtype=np.int64) for _ in range(100)
        )

        # Convert the Torch module to a Numpy module
        numpy_module = NumpyModule(
            self.torch_model,
            dummy_input=torch.from_numpy(inputset[0]),
        )

        # Get the proxy function and parameter mappings used for initializing the compiler
        # This is done in order to be able to provide any modules with arbitrary numbers of 
        # encrypted arguments to Concrete Numpy's compiler
        numpy_filter_proxy, parameters_mapping = generate_proxy_function(
            numpy_module.numpy_forward, 
            ["inputs"]
        )

        # Compile the filter and retrieve its FHE circuit
        compiler = Compiler(
            numpy_filter_proxy,
            {parameters_mapping["inputs"]: "encrypted"},
        )
        self.fhe_circuit = compiler.compile(inputset)

        return self.fhe_circuit

    def post_processing(self, output_image):
        """Apply post-processing to the encrypted output images.

        Args:
            input_image (np.ndarray): The decrypted image to post-process.

        Returns:
            input_image (np.ndarray): The post-processed image.
        """
        # Divide all values if needed
        if self.divide is not None:
            output_image //= self.divide

        # Clip the image's values to proper RGB standards as filters don't handle such constraints
        output_image = output_image.clip(0, 255)

        return output_image
