import torch
from torch import jit
from torchvision.models import efficientnet_b0, efficientnet_b1, efficientnet_b2, efficientnet_b3, efficientnet_b4, efficientnet_b5, efficientnet_b6, efficientnet_b7

# Create a dummy input tensor
fake_input = torch.rand(1, 3, 224, 224)

# List of EfficientNet variants
efficientnet_variants = [
    efficientnet_b0, efficientnet_b1, efficientnet_b2, efficientnet_b3,
    efficientnet_b4, efficientnet_b5, efficientnet_b6, efficientnet_b7
]

for idx, model_fn in enumerate(efficientnet_variants):
    # Load the pretrained model
    model = model_fn(pretrained=True)
    model.eval()

    # Convert the model into a TorchScript module first (using tracing in this case)
    scripted_model = torch.jit.trace(model, fake_input)
    
    # Now freeze the scripted model to remove dynamic behavior
    frozen_model = torch.jit.freeze(scripted_model)
    
    # Run the frozen model on the fake input
    out1 = frozen_model(fake_input).squeeze()
    
    # Save the frozen model
    filename = f"efficientnet_b{idx}.pt"
    frozen_model.save(filename)
    
    # Reload the model and run inference
    loaded_model = torch.jit.load(filename)
    out2 = loaded_model(fake_input).squeeze()
    
    # Print the first five elements of the output from both versions
    print(f"EfficientNet-B{idx} outputs (first 5):", out1[:5], out2[:5])
