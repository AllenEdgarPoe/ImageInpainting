# Image Inpainting Module package
- This Repository is a package for various Image-Inpainting networks, such as EdgeConnect and Generative-contextual-attention model. 

## Requirements
```
pip install torch>=1.7.1
pip install torchvision>=0.8.2
pip install pyyaml
pip install tensorboardX   (pip install tensorflow)
pip install torchsummary>=1.5.1
pip install piq
```

## Implementation
### 1) Prepare Dataset 
- prepare **Visual Genome** dataset 
```
$ bash scripts/download_vg.sh
$ bash scripts/preprocess_vg.sh
```

- prepare **Places2** dataset <br>
Download from [Places2](http://places2.csail.mit.edu/download.html)

- prepare **Irregular Mask** dataset <br>
Download from [Nvidia](https://nv-adlr.github.io/publication/partialconv-inpainting)


### 2) Install Python Requirements
```
pip install -r requirements.txt
```

### 3) Training
```
$ bash train.sh [MODEL_NAME]
```
For example, if you want to train on *Generative Image Inpainting with Contextual Attention*,
```
$ bash train.sh generative-attention
```

### 4) Testing
```
$ bash test.sh [MODEL_NAME]
```
For example, if you test on *Generative Image Inpainting with Contextual Attention*,
the result image will appear in './generate-inpainting/checkpoints/VisualGenome/image'.
