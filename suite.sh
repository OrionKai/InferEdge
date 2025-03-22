#!/bin/bash

main() {
    if [ "$#" -ne 3 ]; then
        echo "Usage: $0 <target address> <target username> <target password>"
        exit 1
    fi

    target_address=$1
    target_username=$2
    target_password=$3

    prompt_user_for_architecture
    prompt_user_for_action
}

function prompt_user_for_architecture() {
    while true; do
        echo "Which of the following architectures does the target machine use?"
            echo "1. x86_64"
            echo "2. aarch64"
        local arch_input
        read -p "Enter the number identifying the architecture: " arch_input
        case $arch_input in
            1) target_architecture="x86_64" ;;
            2) target_architecture="aarch64" ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function prompt_user_for_action() {
    while true; do
        echo "What would you like to do?"
            echo "1. Run the entire suite"
            echo "2. Perform specific actions"
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) run_suite ;;
            2) prompt_user_for_specific_actions ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function prompt_user_for_specific_actions() {
    while true; do
        echo "What would you like to do?"
            echo "1. Acquire files to transfer to target machine"
            echo "2. Transfer files to target machine"
            echo "3. Setup target machine"
            echo "4. Run data collection on target machine"
            echo "5. Retrieve data collection results from target machine"
            echo "6. Run data analysis on host machine"
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) acquire_files ;;
            2) transfer_files ;;
            3) setup_target_machine ;;
            4) run_data_collection ;;
            5) retrieve_data_collection_results ;;
            6) run_data_analysis ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function acquire_files() {
    case $target_architecture in
        "aarch64") acquire_files_aarch64 ;;
        "x86_64") acquire_files_x86_64 ;;
    esac
}

function acquire_files_aarch64() {

}

function acquire_files_x86_64() {

}

main()
