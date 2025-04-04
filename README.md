This directory contains code and assets for the software suite automating performance characterization. A quick summary of each subdirectory's contents is as follows:
* build_scripts: contains shell scripts for building WasmEdge
* cadvisor: contains an editable cAdvisor config file, and will contain the cAdvisor binary when built by the suite
* data_scripts: contains Python scripts for collecting data through experiments and analyzing the results
* docker: contains a Docker installation script, and will contain the Docker image for image classification when built by the suite
* Dockerfiles: contains Dockerfiles for building various Docker images involved in the suite
* host_scripts: contains scripts to be executed on the host machine, including model generation scripts
* inputs: contains inputs for ML inference that will be transferred to the target device
* libtorch: will contain an appropriate LibTorch library when downloaded by the suite
* models: will contain models for ML inference that will be transferred to the target device, including those that the suite will generate
* native: will contain native binaries for ML inference when built by the suite
* prometheus: contains an editable Prometheus config file, and will contain the Prometheus binary when downloaded by the suite
* python: contains requirements.txt files for setting up virtual environments on the host machine
and target device
* results: will store the experimental results retrieved from the target device, and the results of analyzing them as well
* rust: contains ML inference source code
* target_scripts: contains scripts to be executed on the target machine, including the setup script
* wasm: will contain WebAssembly binaries for ML inference when built by the suite
* wasmedge: will contain the WasmEdge binary and related files when built by the suite

A more detailed description of each subdirectory's contents can be read by opening 
the subdirectory's README file. 

To run the suite, grant execute permissions to the script as follows:
`chmod u+x suite.sh`
Then run the following command on the shell:
`./suite.sh`
Note that elements of this script will require sudo permissions, for example when installing
required packages. Note also that an explanation of the suite's functionality can also be found upon
launching the suite and selecting the explanation option.