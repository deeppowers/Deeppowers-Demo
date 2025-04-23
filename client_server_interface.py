"Client-server interface custom implementation for filter models."

from concrete import fhe

from filters import Filter


class FHEServer:
    """Server interface run a FHE circuit."""

    def __init__(self, path_dir):
        """Initialize the FHE interface.

        Args:
            path_dir (Path): The path to the directory where the circuit is saved.
        """
        self.path_dir = path_dir

        # Load the FHE circuit
        self.server = fhe.Server.load(self.path_dir / "server.zip")

    def run(self, serialized_encrypted_image, serialized_evaluation_keys):
        """Run the filter on the server over an encrypted image.

        Args:
            serialized_encrypted_image (bytes): The encrypted and serialized image.
            serialized_evaluation_keys (bytes): The serialized evaluation keys.

        Returns:
            bytes: The filter's output.
        """
        # Deserialize the encrypted input image and the evaluation keys
        encrypted_image = fhe.Value.deserialize(serialized_encrypted_image)
        evaluation_keys = fhe.EvaluationKeys.deserialize(serialized_evaluation_keys)

        # Execute the filter in FHE
        encrypted_output = self.server.run(encrypted_image, evaluation_keys=evaluation_keys)

        # Serialize the encrypted output image
        serialized_encrypted_output = encrypted_output.serialize()

        return serialized_encrypted_output


class FHEDev:
    """Development interface to save and load the filter."""

    def __init__(self, filter, path_dir):
        """Initialize the FHE interface.

        Args:
            filter (Filter): The filter to use in the FHE interface.
            path_dir (str): The path to the directory where the circuit is saved.
        """

        self.filter = filter
        self.path_dir = path_dir

        self.path_dir.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Export all needed artifacts for the client and server interfaces."""
        
        assert self.filter.fhe_circuit is not None, (
            "The model must be compiled before saving it."
        )

        # Save the circuit for the server, using the via_mlir in order to handle cross-platform
        # execution
        path_circuit_server = self.path_dir / "server.zip"
        self.filter.fhe_circuit.server.save(path_circuit_server, via_mlir=True)

        # Save the circuit for the client
        path_circuit_client = self.path_dir / "client.zip"
        self.filter.fhe_circuit.client.save(path_circuit_client)


class FHEClient:
    """Client interface to encrypt and decrypt FHE data associated to a Filter."""

    def __init__(self, path_dir, filter_name, key_dir=None):
        """Initialize the FHE interface.

        Args:
            path_dir (Path): The path to the directory where the circuit is saved.
            filter_name (str): The filter's name to consider.
            key_dir (Path): The path to the directory where the keys are stored. Default to None.
        """
        self.path_dir = path_dir
        self.key_dir = key_dir

        # If path_dir does not exist raise
        assert path_dir.exists(), f"{path_dir} does not exist. Please specify a valid path."

        # Load the client
        self.client = fhe.Client.load(self.path_dir / "client.zip", self.key_dir)

        # Instantiate the filter
        self.filter = Filter(filter_name)

    def generate_private_and_evaluation_keys(self, force=False):
        """Generate the private and evaluation keys.

        Args:
            force (bool): If True, regenerate the keys even if they already exist.
        """
        self.client.keygen(force)

    def get_serialized_evaluation_keys(self):
        """Get the serialized evaluation keys.

        Returns:
            bytes: The evaluation keys.
        """
        return self.client.evaluation_keys.serialize()

    def encrypt_serialize(self, input_image):
        """Encrypt and serialize the input image in the clear.

        Args:
            input_image (numpy.ndarray): The image to encrypt and serialize.

        Returns:
            bytes: The pre-processed, encrypted and serialized image.
        """
        # Encrypt the image
        encrypted_image = self.client.encrypt(input_image)

        # Serialize the encrypted image to be sent to the server
        serialized_encrypted_image = encrypted_image.serialize()
        return serialized_encrypted_image

    def deserialize_decrypt_post_process(self, serialized_encrypted_output_image):
        """Deserialize, decrypt and post-process the output image in the clear.

        Args:
            serialized_encrypted_output_image (bytes): The serialized and encrypted output image.

        Returns:
            numpy.ndarray: The decrypted, deserialized and post-processed image.
        """
        # Deserialize the encrypted image
        encrypted_output_image = fhe.Value.deserialize(
            serialized_encrypted_output_image
        )

        # Decrypt the image
        output_image = self.client.decrypt(encrypted_output_image)

        # Post-process the image
        post_processed_output_image = self.filter.post_processing(output_image)

        return post_processed_output_image
