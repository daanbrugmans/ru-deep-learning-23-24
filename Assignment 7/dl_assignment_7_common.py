# This is a file where you should put your own functions
import math
from typing import Dict, Any

from torch import nn
from torchvision.datasets import MNIST, FashionMNIST
from torch.utils.data import DataLoader
import torchvision
import torch
from d2l import torch as d2l


# -----------------------------------------------------------------------------
# Datasets
# -----------------------------------------------------------------------------
def get_dataset(name: str, batch_size=60, used_data=1.0) -> dict[str, DataLoader[Any]]:
    """
    :param int batch_size: batch size to use for the DataLoaders
    :param str name: name of the dataset to load. Available are 'mnist' and 'fashionmnist'
    :param float used_data: percentage of total dataset to use
    """

    image_transformations = torchvision.transforms.Compose([
        torchvision.transforms.ToTensor(),
        torchvision.transforms.Lambda(lambda image: torch.flatten(image))
    ])

    if name == "mnist":
        train_and_val_data = MNIST(root=".", train=True, download=True, transform=image_transformations)
        test_data = MNIST(root=".", train=False, download=True, transform=image_transformations)
    elif name == "fashionmnist":
        train_and_val_data = FashionMNIST(root=".", train=True, download=True, transform=image_transformations)
        test_data = FashionMNIST(root=".", train=False, download=True, transform=image_transformations)
    else:
        raise ValueError(f"Dataset name {name} was not recognized")

    train_data_count = math.floor(0.9 * len(train_and_val_data) * used_data)
    validation_data_count = math.ceil(0.1 * len(train_and_val_data) * used_data)
    unused_data_count = len(train_and_val_data) - train_data_count - validation_data_count

    train_data, validation_data, _ = torch.utils.data.random_split(
        train_and_val_data, [train_data_count, validation_data_count, unused_data_count]
    )

    test_count = math.ceil(len(test_data) * used_data)
    unused_data_count = len(test_data) - test_count
    test_data, _ = torch.utils.data.random_split(
        test_data, [test_count, unused_data_count]
    )

    return {
        "train": DataLoader(train_data, batch_size, shuffle=True),
        "val": DataLoader(validation_data, batch_size),
        "test": DataLoader(test_data, batch_size)
    }


# -----------------------------------------------------------------------------
# Network architectures
# -----------------------------------------------------------------------------

# TODO: Define network architectures here
def create_lenet(num_classes=10):
    return nn.Sequential(
        # I could not find the activation function used in the paper, but other implementations
        # of LeNet seem to use sigmoid
        nn.LazyLinear(300), nn.Sigmoid(),
        nn.Linear(300, 100), nn.Sigmoid(),
        nn.Linear(100, num_classes)  # , nn.Softmax(dim=0)
    )


def create_arch2():
    raise NotImplementedError()


def create_network(arch, **kwargs):
    # TODO: Change this function for the architectures you want to support
    if arch == 'lenet':
        net = create_lenet(**kwargs)
    elif arch == 'arch2':
        net = create_arch2(**kwargs)
    else:
        raise ValueError(f"Architecture name {arch} was not recognized")
    return net


# def get_weight_init_function(seed):
#     def init_weights_normal(m):
#         # TODO support other layer types
#         if isinstance(m, nn.Linear):
#             torch.nn.init.normal_(m.weight, mean=0.0, std=1.0)
#             torch.nn.init.zeros_(m.bias)


# -----------------------------------------------------------------------------
# Training and testing loops
# -----------------------------------------------------------------------------

# TODO: Define training, testing and model loading here
def evaluate_loss(net: nn, data_iter, loss_fn, device):
    """Evaluate the loss of a model on the given dataset.

    Copied from d2l and slightly modified"""
    metric = d2l.Accumulator(2)  # Sum of losses, no. Of examples

    for x, y in data_iter:
        x = x.to(device)
        y = y.to(device)

        y_hat = net(x)

        loss = loss_fn(y_hat, y)

        metric.add(d2l.reduce_sum(loss), d2l.size(loss))

    return metric[0] / metric[1]


def evaluate(net, evaluation_set, loss_fn, device):
    loss = evaluate_loss(net, evaluation_set, loss_fn, device)
    accuracy = d2l.evaluate_accuracy_gpu(net, evaluation_set, device=device)

    return loss, accuracy


def train(net: nn.Module, data_loaders: Dict[str, DataLoader], optimizer: torch.optim, loss_fn: nn,
          device: str, model_file_name: str, learning_rate: float = 0.0012, epochs: int = 50000,
          eval_every_n_epochs=100):
    # inspired by assignment 5
    """
    Trains the model net with data from the data_loaders['train'], data_loaders['val'], data_loaders['test'].
    """
    net = net.to(device)
    optimizer = optimizer(net.parameters(), lr=learning_rate)

    training_progression_animator = d2l.Animator(
        xlabel='epoch',
        legend=['train loss', 'train accuracy', 'validation loss', 'validation accuracy'],
        figsize=(10, 5)
    )
    training_progression_timer = {'train': d2l.Timer(), 'val': d2l.Timer()}

    for epoch in range(epochs):
        # monitor loss, accuracy, number of samples
        metrics = {'train': d2l.Accumulator(3), 'val': d2l.Accumulator(3)}

        for phase in ('train', 'val'):
            if phase == 'val' and not epoch % eval_every_n_epochs == 0:
                continue
            # switch network to train/eval mode
            net.train(phase == 'train')

            for _, (x, y) in enumerate(data_loaders[phase]):
                training_progression_timer[phase].start()

                x = x.to(device)
                y = y.to(device)

                y_hat = net(x)

                loss = loss_fn(y_hat, y)

                if phase == 'train':
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                loss, accuracy = evaluate(net, data_loaders[phase], loss_fn, device)
                metrics[phase].add(loss * x.shape[0], accuracy * x.shape[0], x.shape[0])

                training_progression_timer[phase].stop()

        if epoch % eval_every_n_epochs == 0:
            path = f"checkpoints/model-{model_file_name}-{epoch}.pth"
            torch.save(net.state_dict(), path)

            training_progression_animator.add(epoch + 1, (
                metrics['train'][0] / metrics['train'][2],
                metrics['train'][1] / metrics['train'][2],
                metrics['val'][0] / metrics['val'][2],
                metrics['val'][1] / metrics['val'][2]
            ))
        else:
            training_progression_animator.add(epoch + 1, (
                metrics['train'][0] / metrics['train'][2],
                metrics['train'][1] / metrics['train'][2]
            ))

    test_loss, test_acc = evaluate(net, data_loaders['test'], loss_fn, device)
    val_loss, val_acc = evaluate(net, data_loaders['val'], loss_fn, device)

    train_loss = metrics['train'][0] / metrics['train'][2]
    train_acc = metrics['train'][1] / metrics['train'][2]

    path = f"checkpoints/model-{model_file_name}-final.pth"
    torch.save(net.state_dict(), path)

    print(f'train loss {train_loss:.3f}, train accuracy {train_acc:.3f}, '
          f'val loss {val_loss:.3f}, val accuracy {val_acc:.3f}, '
          f'test loss {test_loss:.3f}, test accuracy {test_acc:.3f}')

# -----------------------------------------------------------------------------
# Pruning
# -----------------------------------------------------------------------------

# TODO: Put functions related to pruning here
