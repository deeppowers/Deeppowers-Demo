# server.py
from mcp.server.fastmcp import FastMCP, Image as MCPImage
import os
import tempfile
import uuid
import shutil
from pathlib import Path
import requests
import base64
from io import BytesIO
from PIL import Image
import numpy
import urllib.parse

import json

from client_server_interface import FHEClient
from common import FILTERS_PATH, KEYS_PATH, CLIENT_TMP_PATH

# FHE server address
FHE_SERVER_URL = "http://localhost:8000"
# Set HTTP request timeout to 5 minutes
HTTP_TIMEOUT = 300

# Create an MCP server
mcp = FastMCP("FHE-MCP-Server")

def download_image(image_url: str) -> str:
    """Download image from image_url and save to local storage"""
    response = requests.get(image_url, timeout=HTTP_TIMEOUT)
    image_path = f"{CLIENT_TMP_PATH}/{uuid.uuid4()}.jpg"
    with open(image_path, "wb") as f:
        f.write(response.content)
    return image_path

def get_client_file_path(name, id, filter_name):
    """Get the correct temporary file path for the client.

    Args:
        name (str): The desired file name.
        id (str): The unique identifier for the file.
        filter_name (str): The filter chosen by the user

    Returns:
        pathlib.Path: The file path.
    """
    return CLIENT_TMP_PATH / f"{name}_{filter_name}_{id}"


# FHE toolkit
@mcp.tool()
def get_available_filters() -> dict:
    """Get list of available FHE image filters"""
    response = requests.get(f"{FHE_SERVER_URL}/available_filters", timeout=HTTP_TIMEOUT)
    return response.json()

@mcp.tool()
def process_image_with_fhe(
    image_url: str,
    filter_name: str,
) -> dict:
    """Complete process for processing an image using FHE
    
    Args:
        image_path: Input image path
        filter_name: Filter to apply
        output_path: Path to save output image
        
    Returns:
        Processing result information
    """
    # 1. Download image from image_url and save to local storage
    image_path = download_image(image_url)
    user_id = str(uuid.uuid4())
    client = FHEClient(
        FILTERS_PATH / f"{filter_name}/deployment", 
        filter_name,
        key_dir=KEYS_PATH / f"{filter_name}_{user_id}"
    )
    # 1. Generate private key
    key_result = client.generate_private_and_evaluation_keys()
    
    # 2. Encrypt image
    input_image = Image.open(image_path)
    # Ensure image is RGB format, not RGBA
    if input_image.mode != 'RGB':
        input_image = input_image.convert('RGB')
    # Resize to 100x100 as required by the model
    if input_image.size != (100, 100):
        input_image = input_image.resize((100, 100))
    # Convert to numpy array for FHE processing
    input_image_array = numpy.array(input_image)
    # Ensure it's uint8 type, 3 channels (RGB)
    assert input_image_array.shape == (100, 100, 3), f"Incorrect image shape: {input_image_array.shape}"
    encrypt_result = client.encrypt_serialize(input_image_array)
    
    # 3. Prepare request data
    files = [
        ('files', ('encrypted_image.bin', encrypt_result, 'application/octet-stream')),
        ('files', ('evaluation_keys.bin', client.get_serialized_evaluation_keys(), 'application/octet-stream'))
    ]
    data = {
        "user_id": user_id,
        "filter": filter_name
    }

    
    # 4. Execute complete FHE process in one step (replaces the original three requests)
    response = requests.post(
        f"{FHE_SERVER_URL}/fhe_full", 
        data=data, 
        files=files, 
        timeout=HTTP_TIMEOUT
    )
    
    # 5. Get execution time and encrypted output from response
    execution_time = float(response.headers.get("X-FHE-Execution-Time", 0))
    encrypted_output = response.content

    # 6. Save encrypted output data directly, without decryption
    output_id = str(uuid.uuid4())
    output_path = get_client_file_path(f"output", output_id, filter_name)
    with open(output_path, "wb") as f:
        f.write(encrypted_output)  # Save encrypted data, without decryption
    
    return {
        "user_id": user_id,
        "filter_name": filter_name,
        "execution_time": execution_time,
        "output_id": output_id,
        "status": "success"
    }

@mcp.tool()
def decrypt_output_image(user_id: str, filter_name: str, output_id: str) -> str:
    """
    Decrypt output image
    Args:
        user_id: User ID
        filter_name: Filter name
        output_id: Output ID
    Returns:
        str: URL of the decrypted image
    """
    # URL decode filter_name, handle possible spaces and special characters
    decoded_filter_name = urllib.parse.unquote(filter_name)
    
    client = FHEClient(
        FILTERS_PATH / f"{decoded_filter_name}/deployment", 
        decoded_filter_name,
        key_dir=KEYS_PATH / f"{decoded_filter_name}_{user_id}"
    )

    key_result = client.generate_private_and_evaluation_keys()

    output_path = get_client_file_path(f"output", output_id, decoded_filter_name)

    with open(output_path, "rb") as f:
        encrypted_output = f.read()

    # Decrypt data
    decrypted_output = client.deserialize_decrypt_post_process(encrypted_output)

    if isinstance(decrypted_output, bytes):
        # If it's bytes type, need to convert to numpy array
        decrypted_output_array = numpy.frombuffer(decrypted_output, dtype=numpy.uint8).reshape(100, 100, 3)
    else:
        # If it's already a numpy array but not uint8 type, need to convert
        decrypted_output_array = numpy.array(decrypted_output, dtype=numpy.uint8)
        
    # Create PIL image using the converted array
    pil_image = Image.fromarray(decrypted_output_array)
    image_uuid = str(uuid.uuid4())
    # Save as temporary JPG file
    temp_jpg_path = get_client_file_path(f"temp_jpg_{image_uuid}", f"{user_id}.jpeg", decoded_filter_name)
    pil_image.save(temp_jpg_path, format="JPEG")
    
    # Return Test image URL string
    image_filename = temp_jpg_path.name
    return f"{FHE_SERVER_URL}/test/image/{image_filename}"
    # return MCPImage(path=temp_jpg_path)
