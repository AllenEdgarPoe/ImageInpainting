MODEL=$1

if [ $MODEL == "generative-attention" ]; then
    cd generative-inpainting
    python train.py --config '../configs/generative-config.yaml' --psnr True
fi

if [ $MODEL == "edge-connect" ]; then
    cd edge-connect
    echo "Training on 1st Stage\n"
    python train.py --model 1 --checkpoints ./checkpoints/places2
    echo "Training on 2nd Stage\n"
    python train.py --model 2 --checkpoints ./checkpoints/places2
    echo "Training on 3rd Stage\n"
    python train.py --model 3 --checkpoints ./checkpoints/places2


else
    echo "Available arguments are [generative-attention], [edge-connect]"
    exit 1
fi
