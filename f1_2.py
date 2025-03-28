import torch
import torch.nn as nn
import numpy as np

class DDPM(nn.Module):
    def __init__(self, T=1000, beta_schedule='linear', lbeta=1e-4, ubeta=0.02):
        super().__init__()
        self.T = T
        self.beta = self._get_beta_schedule(beta_schedule, lbeta, ubeta)
        self.alpha = 1. - self.beta
        self.alpha_bar = torch.cumprod(self.alpha, dim=0)
        self.sigma = torch.sqrt(self.beta)

    def _get_beta_schedule(self, schedule, lbeta, ubeta):
        if schedule == 'linear':
            return torch.linspace(lbeta, ubeta, self.T)
        elif schedule == 'cosine':
            # Implement cosine schedule
            s = 0.008
            t = torch.arange(self.T) / self.T
            f_t = torch.cos((t + s) / (1 + s) * np.pi / 2) ** 2
            return torch.clip(1 - (f_t / f_t[0]), 0.0, 0.999)
        # Add other schedules if needed

    def diffuse(self, x0, t):
        alpha_bar = self.alpha_bar.to(x0.device)
        eps = torch.randn_like(x0)
        mean = torch.sqrt(alpha_bar[t]) * x0
        var = 1 - alpha_bar[t]
        return mean + torch.sqrt(var) * eps, eps

    def sample(self, model, shape, device):
        xt = torch.randn(shape).to(device)
        for t in reversed(range(self.T)):
            z = torch.randn_like(xt) if t > 0 else 0
            alpha = self.alpha[t]
            alpha_bar = self.alpha_bar[t]
            sigma = self.sigma[t]
            eps_pred = model(xt, torch.tensor([t]).to(device))
            mean = (xt - (1 - alpha)/torch.sqrt(1 - alpha_bar) * eps_pred) / torch.sqrt(alpha)
            xt = mean + sigma * z
        return xt

class UNet(nn.Module):
    def __init__(self, n_channels=1):
        super().__init__()
        self.inc = nn.Conv2d(n_channels, 64, 3, padding=1)
        self.down1 = nn.Conv2d(64, 128, 3, stride=2, padding=1)
        self.down2 = nn.Conv2d(128, 256, 3, stride=2, padding=1)
        self.up1 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.outc = nn.Conv2d(64, n_channels, 3, padding=1)
        self.time_embed = nn.Linear(1, 256)

    def forward(self, x, t, T):
        # Normalize and reshape the time steps
        t = t.float() / T
        t = t.view(-1, 1)  # Reshape to (batch_size, 1)

        # Embed the time steps
        te = self.time_embed(t)

        # Rest of the forward pass
        x1 = torch.relu(self.inc(x))
        x2 = torch.relu(self.down1(x1))
        x3 = torch.relu(self.down2(x2))
        x = torch.relu(self.up1(x3)) + x2
        x = torch.relu(self.up2(x)) + x1
        return self.outc(x)

class DDPM(nn.Module):
    def __init__(self, T=1000, beta_schedule='linear', lbeta=1e-4, ubeta=0.02):
        super().__init__()
        self.T = T
        self.beta = self._get_beta_schedule(beta_schedule, lbeta, ubeta)
        self.alpha = 1. - self.beta
        self.alpha_bar = torch.cumprod(self.alpha, dim=0)
        self.sigma = torch.sqrt(self.beta)

    def _get_beta_schedule(self, schedule, lbeta, ubeta):
        if schedule == 'linear':
            return torch.linspace(lbeta, ubeta, self.T)
        elif schedule == 'cosine':
            s = 0.008
            t = torch.arange(self.T) / self.T
            f_t = torch.cos((t + s) / (1 + s) * np.pi / 2) ** 2
            return torch.clip(1 - (f_t / f_t[0]), 0.0, 0.999)
        else:
            raise ValueError(f"Unknown beta schedule: {schedule}")

    def diffuse(self, x0, t):
        alpha_bar = self.alpha_bar.to(x0.device)

        # Extract alpha_bar values for the given time steps
        alpha_bar_t = alpha_bar[t].view(-1, 1, 1, 1)  # Reshape to (batch_size, 1, 1, 1)

        # Generate noise
        eps = torch.randn_like(x0)

        # Compute mean and variance
        mean = torch.sqrt(alpha_bar_t) * x0  # Broadcast alpha_bar_t across x0
        var = 1 - alpha_bar_t

        # Return noised data and noise
        return mean + torch.sqrt(var) * eps, eps

    def sample(self, model, shape, device):
        xt = torch.randn(shape).to(device)
        for t in reversed(range(self.T)):
            z = torch.randn_like(xt) if t > 0 else 0
            alpha = self.alpha[t].to(device)
            alpha_bar = self.alpha_bar[t].to(device)
            sigma = self.sigma[t].to(device)
            eps_pred = model(xt, torch.tensor([t]).to(device), T=self.T)
            mean = (xt - (1 - alpha) / torch.sqrt(1 - alpha_bar) * eps_pred) / torch.sqrt(alpha)
            xt = mean + sigma * z
        return xt

# Example usage of the sample method
ddpm = DDPM(T=100)
model = UNet().cuda()
xT = torch.randn(16, 1, 32, 32).cuda()  # Example input shape (batch_size, channels, height, width)

with torch.no_grad():
    samples = ddpm.sample(model, xT.shape, device='cuda').cpu().numpy()

print("Samples generated successfully!")

import torch
import torch.nn as nn
import numpy as np

# Define UNet and DDPM classes as above...

# Training loop
def train(model, ddpm, dataloader, optimizer, epochs=100, device='cuda'):
    model.train()
    for epoch in range(epochs):
        for x0 in dataloader:
            x0 = x0.to(device)
            t = torch.randint(0, ddpm.T, (x0.size(0),)).to(device)
            xt, eps = ddpm.diffuse(x0, t)
            eps_pred = model(xt, t, T=ddpm.T)
            loss = nn.MSELoss()(eps_pred, eps)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        print(f'Epoch {epoch} Loss: {loss.item()}')

# Sampling script
ddpm = DDPM(T=100)
model = UNet().cuda()
xT = torch.randn(16, 1, 32, 32).cuda()

with torch.no_grad():
    samples = ddpm.sample(model, xT.shape, device='cuda').cpu().numpy()

np.save('albatross_samples.npy', samples)

Ts = [10, 50, 100, 150, 200]
for T in Ts:
    ddpm = DDPM(T=T)
    model = UNet().cuda()
    print(f"Initialized DDPM with T={T}")

import numpy as np

# Load prior samples
xT = np.load('albatross_prior_samples.npy')
print("Shape of xT:", xT.shape)

# Reshape xT to (batch_size, channels, height, width)
xT = xT.reshape(-1, 1, 8, 8)  # Assuming 8x8 images with 1 channel
print("Reshaped xT:", xT.shape)

import torch
import numpy as np

# Load prior samples
xT = np.load('albatross_prior_samples.npy').astype(np.float32)

# Reshape to (batch_size, channels, height, width)
xT = xT.reshape(-1, 1, 8, 8)  # Adjust dimensions based on your dataset

# Convert to PyTorch tensor
xT = torch.tensor(xT)

# Sample using trained model
model.eval()
with torch.no_grad():
    samples = ddpm.sample(model, xT.shape, device='cuda').cpu().numpy()

# Save generated samples
np.save('albatross_samples.npy', samples)

import matplotlib.pyplot as plt

# Visualize the first sample
sample = xT[0].reshape(8, 8)  # Reshape to 8x8
plt.imshow(sample, cmap='gray')
plt.title("Sample Image")
plt.show()

mv ddpm.py model.py

self.time_embed = nn.Linear(1, 256)

te = self.time_embed(t.float() / T)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# Define the DDPM and UNet classes (as shown earlier)

# Hyperparameters
T = 100
batch_size = 64
epochs = 100
learning_rate = 1e-4

# Create DDPM instance
ddpm = DDPM(T=T)

# Create UNet model
model = UNet().to('cpu')

# Optimizer
optimizer = optim.Adam(model.parameters(), lr=learning_rate)

# Dummy dataset (replace with your actual dataset)
from torch.utils.data import TensorDataset
dummy_data = torch.randn(1000, 1, 8, 8)  # Example: 1000 samples of 8x8 images
dataset = TensorDataset(dummy_data)
dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

# Training loop
def train(model, ddpm, dataloader, optimizer, epochs=100, device='cpu'):
    model.train()
    for epoch in range(epochs):
        for x0, in dataloader:
            x0 = x0.to(device)
            t = torch.randint(0, ddpm.T, (x0.size(0),)).to(device)
            xt, eps = ddpm.diffuse(x0, t)
            eps_pred = model(xt, t, T=ddpm.T)
            loss = nn.MSELoss()(eps_pred, eps)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        print(f'Epoch {epoch} Loss: {loss.item()}')

# Train the model
train(model, ddpm, dataloader, optimizer, epochs=epochs, device='cpu')

# Save the trained model
torch.save(model.state_dict(), 'best_model.pth')
print("Model saved as 'best_model.pth'")

import os

# Check if the file exists
if os.path.exists('best_model.pth'):
    print("File found!")
else:
    print("File not found. Please check the file name and location.")

import torch
import numpy as np

# Define the UNet and DDPM classes (as shown earlier)

# Load pre-trained model
model = UNet()
model.load_state_dict(torch.load('best_model.pth', map_location=torch.device('cpu')))
model.eval()

# Create DDPM instance
ddpm = DDPM(T=100)  # Adjust T based on your trained model

# Load prior samples
xT = torch.tensor(np.load('albatross_prior_samples.npy')).float()

# Reshape xT if necessary (assuming 8x8 images with 1 channel)
xT = xT.reshape(-1, 1, 8, 8)

# Generate samples
with torch.no_grad():
    samples = ddpm.sample(model, xT.shape, device='cpu').cpu().numpy()

# Save generated samples
np.save('albatross_samples_reproduce.npy', samples)
print("Samples generated and saved as 'albatross_samples_reproduce.npy'")

import matplotlib.pyplot as plt

# Load generated samples
generated_samples = np.load('albatross_samples_reproduce.npy')

# Visualize the first few samples
num_samples_to_show = 5
fig, axes = plt.subplots(1, num_samples_to_show, figsize=(15, 3))
for i in range(num_samples_to_show):
    sample = generated_samples[i].reshape(8, 8)  # Reshape to 8x8
    axes[i].imshow(sample, cmap='gray')
    axes[i].axis('off')
plt.show()

!pip install pyemd

import pyemd
print("pyemd installed successfully!")

import numpy as np
from pyemd import emd

def compute_emd(real_samples, generated_samples):
    """
    Compute the Earth Mover Distance (EMD) between real and generated samples.

    Args:
        real_samples (np.ndarray): Real samples of shape (num_samples, channels, height, width).
        generated_samples (np.ndarray): Generated samples of shape (num_samples, channels, height, width).

    Returns:
        float: Earth Mover Distance.
    """
    # Flatten the samples to 1D vectors
    real_flat = real_samples.reshape(real_samples.shape[0], -1)
    gen_flat = generated_samples.reshape(generated_samples.shape[0], -1)

    # Compute pairwise distances
    distance_matrix = np.sqrt(np.sum((real_flat[:, None, :] - gen_flat[None, :, :]) ** 2, axis=-1))

    # Normalize histograms
    hist_real = np.ones(real_flat.shape[0]) / real_flat.shape[0]
    hist_gen = np.ones(gen_flat.shape[0]) / gen_flat.shape[0]

    # Compute EMD
    return emd(hist_real, hist_gen, distance_matrix)

import torch

def compute_nll(model, generated_samples):
    """
    Compute the Negative Log-Likelihood (NLL) of generated samples.

    Args:
        model (torch.nn.Module): Trained DDPM model.
        generated_samples (np.ndarray): Generated samples of shape (num_samples, channels, height, width).

    Returns:
        float: Negative Log-Likelihood.
    """
    # Convert samples to PyTorch tensor
    generated_samples = torch.tensor(generated_samples, dtype=torch.float32)

    # Compute log probabilities (simplified example)
    with torch.no_grad():
        log_probs = model(generated_samples).log_prob(generated_samples)

    # Return the mean negative log-likelihood
    return -log_probs.mean().item()

from utils import get_emd, get_nll

import os

# Check if the file exists
if os.path.exists('albatross_real_samples.npy'):
    print("File found!")
else:
    print("File not found. Please check the file name and location.")

import numpy as np

# Load real samples (file name updated)
real_samples = np.load('albatross_samples.npy')  # Real data
real_samples = real_samples.reshape(-1, 1, 8, 8)  # Reshape to (batch_size, channels, height, width)

# Load generated samples
generated_samples = np.load('albatross_samples_reproduce.npy')  # Generated data
generated_samples = generated_samples.reshape(-1, 1, 8, 8)  # Reshape to (batch_size, channels, height, width)

import numpy as np

# Load real samples (file name updated)
real_samples = np.load('albatross_samples.npy')  # Real data
real_samples = real_samples.reshape(-1, 1, 8, 8)  # Reshape to (batch_size, channels, height, width)

# Load generated samples
generated_samples = np.load('albatross_samples_reproduce.npy')  # Generated data
generated_samples = generated_samples.reshape(-1, 1, 8, 8)  # Reshape to (batch_size, channels, height, width)

from utils import get_emd

# Flatten the samples for EMD computation
real_flat = real_samples.reshape(real_samples.shape[0], -1)
gen_flat = generated_samples.reshape(generated_samples.shape[0], -1)

# Compute EMD
emd_score = get_emd(real_flat, gen_flat)
print(f"Earth Mover Distance: {emd_score}")

from utils import get_nll
import torch

# Convert samples to PyTorch tensors for NLL computation
real_tensor = torch.tensor(real_flat, dtype=torch.float32)
gen_tensor = torch.tensor(gen_flat, dtype=torch.float32)

# Compute NLL
temperature = 1e-1  # Adjust temperature if needed
nll_score = get_nll(real_tensor, gen_tensor, temperature=temperature)
print(f"Negative Log-Likelihood: {nll_score.item()}")



import torch
import numpy as np

# Define the UNet and DDPM classes (as shown earlier)

# Load pre-trained model
model = UNet()
model.load_state_dict(torch.load('best_model.pth', map_location=torch.device('cpu')))
model.eval()

# Create DDPM instance
ddpm = DDPM(T=100)  # Adjust T based on your trained model

# Load prior samples
xT = torch.tensor(np.load('albatross_prior_samples.npy')).float()

# Reshape xT if necessary (assuming 8x8 images with 1 channel)
xT = xT.reshape(-1, 1, 8, 8)

# Generate samples
with torch.no_grad():
    samples = ddpm.sample(model, xT.shape, device='cpu').cpu().numpy()

# Save generated samples
np.save('albatross_samples_reproduce.npy', samples)
print("Samples generated and saved as 'albatross_samples_reproduce.npy'")