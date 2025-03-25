import os
import torch
from torch import jit

with torch.no_grad():
    # Create a dummy input tensor
    fake_input = torch.rand(1, 3, 224, 224)

    # Load the pretrained model
    model = torch.hub.load('pytorch/vision:v0.10.0',
                           'mobilenet_v2', pretrained=True)
    model.eval()

    # Convert the model into a TorchScript module using scripting
    sm = torch.jit.script(model)

    # Save the model
    sm.save("mobilenet.pt")
