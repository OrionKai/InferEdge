import torch
from torch import jit
from torchvision.models import (
    resnet18, resnet34, resnet50, resnet101, resnet152,
    ResNet18_Weights, ResNet34_Weights, ResNet50_Weights, ResNet101_Weights, ResNet152_Weights
)

# Create a dummy input tensor
fake_input = torch.rand(1, 3, 224, 224)

# List of ResNet variants, their weights, and corresponding numbers
resnet_variants = [resnet18, resnet34, resnet50, resnet101, resnet152]
resnet_weights = [ResNet18_Weights.DEFAULT, ResNet34_Weights.DEFAULT, ResNet50_Weights.DEFAULT,
                  ResNet101_Weights.DEFAULT, ResNet152_Weights.DEFAULT]
resnet_numbers = [18, 34, 50, 101, 152]

for idx, model_fn in enumerate(resnet_variants):
    # Load the model with the new weights API
    model = model_fn(weights=resnet_weights[idx])
    model.eval()
    
    # Run the model on the fake input
    out1 = model(fake_input).squeeze()
    
    # Trace the model with TorchScript and save it
    traced_model = jit.trace(model, fake_input)
    filename = f"resnet{resnet_numbers[idx]}.pt"
    traced_model.save(filename)
    
    # Reload the model and run inference
    loaded_model = jit.load(filename)
    out2 = loaded_model(fake_input).squeeze()
    
    # Print the first five elements of the output from both versions
    print(f"ResNet-{resnet_numbers[idx]} outputs (first 5):", out1[:5], out2[:5])
