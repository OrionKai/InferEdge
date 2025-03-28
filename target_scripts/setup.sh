#!/bin/bash
# This script is meant to be run on the target machine to perform one-time setup of the environment 
# in preparation for the experiments.

export USERNAME=${SUDO_USER:-$(whoami)}
export SUITE_PATH="/home/$USERNAME/Desktop/CS4099Suite"

function main() {
    if [ "$(uname -m)" == "aarch64" ]; then
        arch="arm64"
    else
        arch="amd64"
    fi

    apt-get update

    setup_wasmedge

    if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
        # cgroup v2 is active, must enable memory controller
        enable_memory_controller
    fi

    install_time
    setup_docker
    load_docker_image
    setup_cadvisor
    setup_prometheus
    setup_python
    setup_collect_data
    # TODO: test if Darwin actually shows up on Ubuntu VM on Mac, else ask interactively
    # Setup LD_LIBRARY_PATH in preparation for AoT compilation
    export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:$SUITE_PATH/libtorch/lib
    if [ "$(uname)" != "Darwin" ]; then
        aot_compile_wasm_non_mac
    else
        aot_compile_wasm_mac
    fi
}

function install_time() {
    apt-get install -y time
}

function setup_wasmedge() {
    chmod u+x "/home/$USERNAME/.wasmedge/bin/wasmedge"

    # Add wasmedge to the PATH for the remainder of this script
    # since it will be used in various parts
    export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin


    # Create symbolic links in case they were not uploaded 
    ln -s "/home/$USERNAME/.wasmedge/lib64/libwasmedge.so.0.1.0" "/home/$USERNAME/.wasmedge/lib64/libwasmedge.so"
    ln -s "/home/$USERNAME/.wasmedge/lib64/libwasmedge.so.0.1.0" "/home/$USERNAME/.wasmedge/lib64/libwasmedge.so.0"
}

function enable_memory_controller() {
    # This function is sometimes required if the memory controller is not enabled
    # by default, for cgroup v2 devices
    local cmdline_file="/boot/firmware/cmdline.txt"
    local cgroup_enable_param="cgroup_enable=memory"
    local current_cmdline_contents="$(cat "$cmdline_file")"

    if ! grep -q "$cgroup_enable_param" <<< "$current_cmdline_contents"
    then 
        cp "$cmdline_file" "$cmdline_file.bak"
        local new_cmdline_contents="${current_cmdline_contents} ${cgroup_enable_param}"
        sh -c "echo '$new_cmdline_contents' > $cmdline_file"
    fi
}

function setup_docker() {
    if ! command -v docker &> /dev/null; then
        echo "Docker is not installed. Would you like to install Docker through the script?"
            echo "1. Yes"
            echo "2. No"
        read -p "Enter the number identifying your choice: " choice
        if [ "$choice" == "1" ]; then
            chmod u+x "$SUITE_PATH/docker/install-docker.sh"
            "$SUITE_PATH"/docker/install-docker.sh
        else
            echo "Please install Docker manually and re-run this script."
            exit 1
        fi
    fi
}

function load_docker_image() {
    docker load -i "$SUITE_PATH/docker/image-classification-$arch.tar"
}

function setup_cadvisor() {
    chmod u+x "$SUITE_PATH/cadvisor/cadvisor"
    apt install libpfm4 linux-perf
}

function setup_prometheus() {
    chmod u+x "$SUITE_PATH/prometheus/prometheus"
}

function setup_python() {
    # Check if Python is installed, if not, install it
    if ! command -v python3 &> /dev/null
    then
        echo "Python3 is not installed. Would you like to install Python3 through the script?"
            echo "1. Yes"
            echo "2. No"
        read -p "Enter the number identifying your choice: " choice
        if [ "$choice" == "1" ]; then
            apt install -y python3 python3-venv python3-pip
        else
            echo "Please install Python3 manually and re-run this script."
            exit 1
        fi
    fi

    apt install -y cgroup-tools
    python3 -m venv "$SUITE_PATH/myenv" 
    source "$SUITE_PATH/myenv/bin/activate" && pip install -r "$SUITE_PATH/python/target/requirements.txt"
}

function setup_collect_data() {
    chmod u+x "$SUITE_PATH/target_scripts/collect_data.sh"
}

function aot_compile_wasm_non_mac() {
    # AoT compile the WebAssembly code (if not on Mac)
    wasmedge compile "$SUITE_PATH/wasm/interpreted.wasm" "$SUITE_PATH/wasm/aot.wasm"
}

function aot_compile_wasm_mac() {
    # AoT compile the WebAssembly code (if on Mac)
    wasmedge compile "$SUITE_PATH/wasm/interpreted.wasm" "$SUITE_PATH/wasm/aot.so"
}

main