"""Server that will listen for GET and POST requests from the client."""

import time
from typing import List
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response

from common import FILTERS_PATH, SERVER_TMP_PATH, AVAILABLE_FILTERS, CLIENT_TMP_PATH
from client_server_interface import FHEServer

# Load the server objects related to all currently available filters once and for all
FHE_SERVERS = {
    filter: FHEServer(FILTERS_PATH / f"{filter}/deployment") for filter in AVAILABLE_FILTERS
}

def get_server_file_path(name, user_id, filter_name):
    """Get the correct temporary file path for the server.

    Args:
        name (str): The desired file name.
        user_id (int): The current user's ID.
        filter_name (str): The filter chosen by the user

    Returns:
        pathlib.Path: The file path.
    """
    return SERVER_TMP_PATH / f"{name}_{filter_name}_{user_id}"


# Initialize an instance of FastAPI
app = FastAPI()

# Define the default route
@app.get("/")
def root():
    return {"message": "Welcome to Image FHE Filter Server!"}

@app.get("/available_filters")
def get_available_filters():
    return {"filters": AVAILABLE_FILTERS}


@app.post("/send_input")
def send_input(
    user_id: str = Form(),
    filter: str = Form(),
    files: List[UploadFile] = File(),
):
    """Send the inputs to the server."""
    # Retrieve the encrypted input image and the evaluation key paths
    encrypted_image_path = get_server_file_path("encrypted_image", user_id, filter)
    evaluation_key_path = get_server_file_path("evaluation_key", user_id, filter)
    
    # Write the files using the above paths
    with encrypted_image_path.open("wb") as encrypted_image, evaluation_key_path.open(
        "wb"
    ) as evaluation_key:
        encrypted_image.write(files[0].file.read())
        evaluation_key.write(files[1].file.read())


@app.post("/run_fhe")
def run_fhe(
    user_id: str = Form(),
    filter: str = Form(),
):
    """Execute the filter on the encrypted input image using FHE."""
    # Retrieve the encrypted input image and the evaluation key paths
    encrypted_image_path = get_server_file_path("encrypted_image", user_id, filter)
    evaluation_key_path = get_server_file_path("evaluation_key", user_id, filter)

    # Read the files using the above paths
    with encrypted_image_path.open("rb") as encrypted_image_file, evaluation_key_path.open(
        "rb"
    ) as evaluation_key_file:
        encrypted_image = encrypted_image_file.read()
        evaluation_key = evaluation_key_file.read()

    # Load the FHE server related to the chosen filter
    fhe_server = FHE_SERVERS[filter]

    # Run the FHE execution
    start = time.time()
    encrypted_output_image = fhe_server.run(encrypted_image, evaluation_key)
    fhe_execution_time = round(time.time() - start, 2)

    # Retrieve the encrypted output image path
    encrypted_output_path = get_server_file_path("encrypted_output", user_id, filter)

    # Write the file using the above path
    with encrypted_output_path.open("wb") as encrypted_output:
        encrypted_output.write(encrypted_output_image)

    return JSONResponse(content=fhe_execution_time)


@app.post("/get_output")
def get_output(
    user_id: str = Form(),
    filter: str = Form(),
):
    """Retrieve the encrypted output image."""
    # Retrieve the encrypted output image path
    encrypted_output_path = get_server_file_path("encrypted_output", user_id, filter)

    # Read the file using the above path
    with encrypted_output_path.open("rb") as encrypted_output_file:
        encrypted_output = encrypted_output_file.read()

    return Response(encrypted_output)


@app.post("/fhe_full")
def fhe_full(
    user_id: str = Form(),
    filter: str = Form(),
    files: List[UploadFile] = File(),
):
    """Execute the complete FHE process: receive input, run FHE computation and return the result.
    Sequentially executes the business logic of /send_input, /run_fhe, and /get_output.
    """
    # Step 1: Save the uploaded encrypted image and evaluation key (/send_input logic)
    encrypted_image_path = get_server_file_path("encrypted_image", user_id, filter)
    evaluation_key_path = get_server_file_path("evaluation_key", user_id, filter)
    
    with encrypted_image_path.open("wb") as encrypted_image, evaluation_key_path.open(
        "wb"
    ) as evaluation_key:
        encrypted_image.write(files[0].file.read())
        evaluation_key.write(files[1].file.read())
    print("Encrypted image and evaluation key saved")
    
    # Step 2: Execute FHE computation (/run_fhe logic)
    with encrypted_image_path.open("rb") as encrypted_image_file, evaluation_key_path.open(
        "rb"
    ) as evaluation_key_file:
        encrypted_image = encrypted_image_file.read()
        evaluation_key = evaluation_key_file.read()

    fhe_server = FHE_SERVERS[filter]
    print("FHE server initialization completed")
    start = time.time()
    encrypted_output_image = fhe_server.run(encrypted_image, evaluation_key)
    fhe_execution_time = round(time.time() - start, 2)
    print("FHE computation completed")
    
    encrypted_output_path = get_server_file_path("encrypted_output", user_id, filter)
    
    with encrypted_output_path.open("wb") as encrypted_output:
        encrypted_output.write(encrypted_output_image)
    print("Encrypted output image saved")
    
    # Step 3: Return the encrypted output result (/get_output logic)
    with encrypted_output_path.open("rb") as encrypted_output_file:
        encrypted_output = encrypted_output_file.read()
    print("Returning encrypted output result completed")
    
    # Return FHE execution time information and encrypted output image
    return Response(
        content=encrypted_output,
        headers={
            "X-FHE-Execution-Time": f"{fhe_execution_time}",
        }
    )

@app.get("/test/image/{image_name}")
def test_image(image_name: str):
    """Just for testing the image."""
    image_path = CLIENT_TMP_PATH / image_name
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    return Response(content=image_data, media_type="image/jpeg")

# Start the server when this script is run directly
if __name__ == "__main__":
    import uvicorn
    print("Starting FHE server...")
    print("Server address: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
