"A script to generate all development files necessary for the image filtering demo."

import shutil
from common import AVAILABLE_FILTERS, FILTERS_PATH
from filters import Filter
from client_server_interface import FHEDev

print("Generating deployment files for all available filters")

def generate_dev_files():
    filter_files_path = []
    for filter_name in AVAILABLE_FILTERS:
        print("Filter:", filter_name, "\n")

        # Create the filter instance
        filter = Filter(filter_name)

        # Compile the model on a representative inputset
        filter.compile()

        # Define the directory path associated to this filter's deployment files
        deployment_path = FILTERS_PATH / (filter_name + "/deployment")

        # Delete the deployment folder and its content if it already exists
        if deployment_path.is_dir():
            shutil.rmtree(deployment_path)

        # Save the files needed for deployment
        fhe_dev_filter = FHEDev(filter, deployment_path)
        fhe_dev_filter.save()
        filter_files_path.append(deployment_path)

    return filter_files_path

