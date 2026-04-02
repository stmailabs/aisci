# Title: Task-Adaptive Metric Generation via Lightweight Hypernetworks for Few-Shot Classification

## Keywords
few-shot learning, meta-learning, hypernetworks, task-adaptive metrics, metric learning

## TL;DR
We explore using lightweight hypernetworks to generate task-specific distance metrics for few-shot classification, replacing fixed metrics with learned, per-task Mahalanobis-like transformations conditioned on support sets.

## Abstract
Few-shot classification methods based on metric learning — such as Prototypical Networks and Matching Networks — typically rely on a single, fixed distance function (Euclidean or cosine) applied uniformly across all tasks. However, different few-shot tasks may exhibit vastly different intra-class variance structures, suggesting that a one-size-fits-all metric is suboptimal. Prior work such as TADAM introduced task-dependent feature transformations, but these approaches often require substantial architectural overhead or task-specific fine-tuning that scales poorly.

This workshop investigates a lightweight alternative: small hypernetworks that take the support set embedding as input and output a per-task metric transformation matrix (e.g., a low-rank Mahalanobis matrix or a diagonal scaling vector). The key research questions include: (1) Can a compact hypernetwork (a few thousand parameters) meaningfully improve over fixed metrics on standard benchmarks? (2) How should the hypernetwork be conditioned — on prototype statistics, set-level features, or individual support examples? (3) What is the trade-off between metric expressiveness (full matrix vs. diagonal vs. low-rank) and few-shot generalization?

We welcome contributions that propose novel architectures for metric generation, provide theoretical analysis of task-adaptive metrics in the few-shot regime, or conduct systematic ablation studies comparing conditioning strategies and metric parameterizations. Experiments should target standard benchmarks (mini-ImageNet 5-way 1-shot/5-shot, CIFAR-FS, Omniglot) with lightweight backbones (4-layer ConvNet or ResNet-12) to ensure reproducibility and accessibility. Negative results — e.g., demonstrating when adaptive metrics fail to improve over fixed ones — are equally valuable.
