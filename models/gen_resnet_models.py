import torch
from torch import jit
from torchvision.models import (
    resnet18, resnet34, resnet50, resnet101, resnet152,
    ResNet18_Weights, ResNet34_Weights, ResNet50_Weights, ResNet101_Weights, ResNet152_Weights
)
import argparse

def main():
    # Parse input arguments representing which variants to generate
    parser = argparse.ArgumentParser()
    parser.add_argument("--resnet18", action="store_true", help="Generate ResNet-18")
    parser.add_argument("--resnet34", action="store_true", help="Generate ResNet-34")
    parser.add_argument("--resnet50", action="store_true", help="Generate ResNet-50")
    parser.add_argument("--resnet101", action="store_true", help="Generate ResNet-101")
    parser.add_argument("--resnet152", action="store_true", help="Generate ResNet-152")
    args = parser.parse_args()

    resnet_variants = []
    resnet_weights = []
    resnet_numbers = []

    if args.resnet18:
        resnet_variants.append(resnet18)
        resnet_weights.append(ResNet18_Weights.DEFAULT)
        resnet_numbers.append(18)
    if args.resnet34:
        resnet_variants.append(resnet34)
        resnet_weights.append(ResNet34_Weights.DEFAULT)
        resnet_numbers.append(34)
    if args.resnet50:
        resnet_variants.append(resnet50)
        resnet_weights.append(ResNet50_Weights.DEFAULT)
        resnet_numbers.append(50)
    if args.resnet101:
        resnet_variants.append(resnet101)
        resnet_weights.append(ResNet101_Weights.DEFAULT)
        resnet_numbers.append(101)
    if args.resnet152:
        resnet_variants.append(resnet152)
        resnet_weights.append(ResNet152_Weights.DEFAULT)
        resnet_numbers.append(152)

    generate_resnet_models(resnet_variants, resnet_weights, resnet_numbers)

def generate_resnet_models(resnet_variants, resnet_weights, resnet_numbers):
    # Create a dummy input
    fake_input = torch.rand(1, 3, 224, 224)

    for idx, model_fn in enumerate(resnet_variants):
        # Load the pretrained model
        model = model_fn(weights=resnet_weights[idx])
        model.eval()
        
        # Convert the model into a TorchScript module using tracing,
        # passing in the dummy input to trace
        traced_model = jit.trace(model, fake_input)

        # Save the frozen model
        filename = f"resnet{resnet_numbers[idx]}.pt"
        traced_model.save(filename)

if __name__ == "__main__":
    main()