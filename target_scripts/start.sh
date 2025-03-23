# This script is meant to be run on the Raspberry Pi to perform the data collection experiments for a number
# of different models and inputs.
USERNAME=$(whoami)

cd Desktop/Benchmark

export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/$USERNAME/.wasmedge/lib64:/home/$USERNAME/libtorch/lib
export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin

source scripts/myenv/bin/activate

export TRIALS=50

# TODO: sometimes squeezenet execution finishes so fast that cAdvisor doesn't capture the metrics
# echo "Running collect_data.py with squeezenet.pt and input.jpg"
# python collect_data.py --model squeezenet.pt --input input.jpg --trials $TRIALS

# for image in inputs/*; do
#     if [[ -f "$image" ]]; then
#         echo "Running collect_data.py with mobilenet.pt and $image"
#         python collect_data.py --model mobilenet.pt --input "$(basename "$image")" --trials $TRIALS
#     fi
# done

# echo "Running collect_data.py with efficientnet.pt and input.jpg"
# python collect_data.py --model efficientnet.pt --input input.jpg --trials $TRIALS

# echo "Running collect_data.py with mobilenet.pt and seal.jpg"
# python collect_data.py --model mobilenet.pt --input seal.jpg --trials $TRIALS

echo "Running collect_data.py with mobilenet.pt and input.jpg"
python collect_data.py --model mobilenet.pt --input input.jpg --trials $TRIALS




