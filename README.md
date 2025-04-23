# FHE Image Processing Server

This project demonstrates a server-based application for applying image filters using Fully Homomorphic Encryption (FHE). It allows for secure image processing where the server never sees the unencrypted image content.

## Overview

The system consists of two main components:
- **FHE Server**: Processes encrypted images without decrypting them
- **MCP Server**: Client interface that handles image preparation, encryption, and decryption

## Features

- Apply various image filters to encrypted images
- Complete FHE workflow: encryption, processing, and decryption
- Process images while preserving privacy through homomorphic encryption
- RESTful API for client integration

## Architecture

The system follows a client-server architecture:

1. The client sends an image URL to the MCP server
2. MCP server:
   - Downloads the image
   - Generates encryption keys
   - Encrypts the image
   - Sends the encrypted image to the FHE server
3. FHE server:
   - Processes the encrypted image without decryption
   - Returns the encrypted result
4. MCP server:
   - Stores the encrypted output
   - Can decrypt the result when requested

## Setup

### Prerequisites

- Python 3.11.4
- uv package installer (faster alternative to pip)

### Installation

1. Clone the repository

2. Install MCP CLI:
   ```
   uv add "mcp[cli]"
   ```

3. Initialize filters:
   ```
   uv run generate_dev_files.py
   ```

4. Install MCP server to Claude Desktop:
   ```
   uv run mcp install mcp_server.py
   ```

   If `uv run mcp install mcp_server.py` doesn't work in your Claude Desktop, you can try to config `bash {project_path}/mcp_server.exmaple.sh` and replace `{project_path}` with your project path.

## Usage

### Starting the Servers

1. Start the FHE server:
   ```
   uv run fhe_server.py
   ```
   This will run on http://localhost:8000 by default

2. You can now access the MCP server through Claude Desktop

### API Endpoints

#### FHE Server Endpoints:

- `GET /`: Welcome message
- `GET /available_filters`: List available filters
- `POST /send_input`: Upload encrypted image and evaluation key
- `POST /run_fhe`: Execute FHE computation
- `POST /get_output`: Retrieve encrypted output
- `POST /fhe_full`: Complete FHE workflow in a single request
- `GET /test/image/{image_name}`: Test endpoint for viewing images

#### MCP Server Tools:

- `get_available_filters()`: Get list of available FHE filters
- `process_image_with_fhe(image_url, filter_name)`: Process an image through the FHE pipeline
- `decrypt_output_image(user_id, filter_name, output_id)`: Decrypt processed image

## Notes

- The system resizes images to 100x100 pixels for processing
- Encryption/decryption keys are generated per session
- Processed images are temporarily stored in the configured temp directories

## Security Considerations

This demo implements FHE for educational purposes. In a production environment, additional security measures should be implemented:
- Secure key management
- HTTPS for all API communication
- Authentication and authorization
- Proper data retention policies
